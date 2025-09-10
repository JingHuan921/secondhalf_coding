from typing import Any, Dict, List, Union, Optional, Annotated
import os
import json
import asyncio
from operator import add

from backend.path_global_file import PROMPT_DIR_ANALYST
from backend.utils.main_utils import (
    load_prompts, generate_plantuml_local, extract_plantuml, pydantic_to_json_text
)
from backend.graph_logic.state import (
    AgentType, ArtifactType, Artifact, Conversation, ArtifactState, StateManager,
    create_artifact, create_conversation, add_artifacts, add_conversations, 
     _get_latest_version, _increment_version, _create_versioned_artifact
)
from backend.artifact_model import RequirementsClassificationList, SystemRequirementsList, RequirementsModel

from pydantic import BaseModel

from langchain_core.tools import tool 
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode


import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from operator import add


# This loads all key-value pairs from a .env file into os.environ
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")



# Load prompt library once
prompt_path = PROMPT_DIR_ANALYST
PROMPT_LIBRARY = load_prompts(prompt_path)


llm = init_chat_model("openai:gpt-4.1")


# First node: Process user input and convert to conversation
def process_user_input(state: ArtifactState) -> ArtifactState:
    """
    First node: Convert user input to conversation entry
    This is the entry point that processes the user input from LangGraph Studio
    """
    try:
        # Check if there's user input
        if not state.human_request or state.human_request.strip() == "":
            return {
                "errors": ["No user input provided"],
            }
        
        user_input = state.human_request.strip()
        
        # Create conversation entry for user input
        user_conversation = create_conversation(
            agent=AgentType.USER,
            artifact_id=None,  # No artifact yet for user input
            content=user_input,
        )
        
        return {
            "conversations": [user_conversation]
        }
        
    except Exception as e:
        return {
            "errors": [f"Failed to process user input: {str(e)}"]
        }


# Example usage in workflow nodes
async def classify_user_requirements(state: ArtifactState) -> ArtifactState:

    try:
        llm_with_structured_output = llm.with_structured_output(RequirementsClassificationList)
        system_prompt = PROMPT_LIBRARY.get("classify_user_reqs")

        if not system_prompt:
            raise ValueError("Missing 'classify_user_reqs' prompt in prompt library.")
        
        
        response = await llm_with_structured_output.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state.conversations[-1].content)
        ]
        )
        converted_text = await pydantic_to_json_text(response)


        # Create artifact using factory function
        artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.REQ_CLASS,
            content=response,  
        )
        
        # Create conversation entry
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=artifact.id,
            content=converted_text
        )
        
        return {
            "artifacts": [artifact],  
            "conversations": [conversation],  
        }
        
    except Exception as e:
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }

async def write_system_requirement (state: ArtifactState) -> ArtifactState:

    try: 
        llm_with_structured_output = llm.with_structured_output(SystemRequirementsList)
        system_prompt = PROMPT_LIBRARY.get("write_system_req")

        if not system_prompt:
            raise ValueError("Missing 'write_system_req' prompt in prompt library.")

        response = await llm_with_structured_output.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state.conversations[-1].content)
        ]
        )
        converted_text = await pydantic_to_json_text(response)

        
        # Create artifact using factory function
        artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.SYSTEM_REQ,
            content=response,  
        )
        
        # Create conversation entry
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=artifact.id,
            content=converted_text
        )

        return {
            "artifacts": [artifact],  # Will be added via reducer
            "conversations": [conversation],  # Will be added via reducer
        }
        
    except Exception as e:
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }
    
async def generate_use_case_diagram(uml_code: str) -> str:
    """
    Generate a use case diagram from PlantUML code

    Args:
        uml_code: The PlantUML code to generate diagram from
        output_location: Optional base directory for output (defaults to script parent directory)

    Returns:
        Path to the generated diagram file or error message
    """
    try:
        result = await generate_plantuml_local(uml_code=uml_code)  # <-- await here
        if result:
            return f"Use case diagram generated successfully at: {result}"
        else:
            return "Failed to generate use case diagram. Check PlantUML installation and code syntax."
    except Exception as e:
        return f"Error generating diagram: {str(e)}"
        

async def build_requirement_model(state: ArtifactState) -> ArtifactState:
    """
    Build requirement model, extract UML, generate diagram, and return UML chunk
    """
    try:
        system_prompt = PROMPT_LIBRARY.get("build_req_model")

        if not system_prompt:
            raise ValueError("Missing 'build_req_model' prompt in prompt library.")
        
        # Get the LLM response
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state.conversations[-1].content)
        ])
        
        # Extract PlantUML code from the response
        uml_chunk = None
        diagram_generation_message = "No PlantUML code found in response."
        
        if hasattr(response, 'content') and response.content:
            try:
                # Extract the UML chunk using your existing function
                uml_chunk = extract_plantuml(response.content)
                
                # Generate the diagram using the tool
                diagram_result = await generate_use_case_diagram(
                    uml_code = uml_chunk
                )
                diagram_generation_message = diagram_result
                
            except ValueError:
                # No PlantUML code found
                uml_chunk = None
                diagram_generation_message = "No PlantUML code found in the LLM response."
            except Exception as e:
                # Error during diagram generation
                diagram_generation_message = f"Error generating diagram: {str(e)}"
        
        # Create final response - return the UML chunk if found, otherwise original response
        if uml_chunk:
            # Return just the UML chunk as the final response
            final_response_content = uml_chunk
            print(f"Diagram generation: {diagram_generation_message}")  # Log the diagram result
        else:
            # If no UML found, return the original response
            final_response_content = response.content if hasattr(response, 'content') else str(response)
            print(f"No UML extracted: {diagram_generation_message}")
        
        # Create artifact using factory function
        artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.REQ_MODEL,
            content=final_response_content,  
        )
        
        # Create conversation entry
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=artifact.id,
            content=final_response_content,
        )

        return {
            "artifacts": [artifact],  
            "conversations": [conversation],  
        }
    
    except Exception as e:
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }
    



# Define a new graph
workflow = StateGraph(ArtifactState)
workflow.add_node("process_user_input", process_user_input)
workflow.add_node("classify_user_requirements", classify_user_requirements)
workflow.add_node("write_system_requirement", write_system_requirement)
workflow.add_node("build_requirement_model", build_requirement_model)

"""
add for routing function and deciding node 
"""



# Set the entrypoint as `agent`
workflow.set_entry_point("process_user_input")
workflow.add_edge("process_user_input", "classify_user_requirements")
workflow.add_edge("classify_user_requirements", "write_system_requirement")
workflow.add_edge("write_system_requirement", "build_requirement_model")

"""
add routing function to write_req_specs node or to another routing function (before END)
"""
workflow.add_edge("build_requirement_model", END)
graph = workflow.compile()


if __name__ == "__main__":
    prompt = PROMPT_LIBRARY.get("classify_user_reqs")
    human_input = prompt
    
    answer = graph.invoke(input={"messages": [("human", human_input)]})["final_response"]
    print(answer.model_dump_json(indent=2))