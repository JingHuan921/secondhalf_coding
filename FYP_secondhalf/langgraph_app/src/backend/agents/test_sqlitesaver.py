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
    AgentType, ArtifactType, ArtifactMetadata, Artifact, Conversation, AgentState, StateManager,
    create_artifact, create_conversation, add_artifacts, add_conversations, 
     _get_latest_version, _increment_version, _create_versioned_artifact
)
from backend.artifact_model import RequirementsClassificationList, SystemRequirementsList, RequirementsModel, SoftwareRequirementSpecs

from pydantic import BaseModel
#checkpointing modules
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


from langchain_core.tools import tool 
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
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
def process_user_input(state):
    # Check if user_input already exists in state
    user_input = state.get("user_input")
    
    # If not, prompt for it
    if not user_input:
        user_input = input("Enter your requirements: ")
    
    # Validate input
    if not user_input or user_input.strip() == "":
        return {"error": "No user input provided"}
    
    return {"user_input": user_input.strip()}

# Example usage in workflow nodes
async def classify_user_requirements(state: AgentState) -> AgentState:

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

async def write_system_requirement (state: AgentState) -> AgentState:

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
        

async def build_requirement_model(state: AgentState) -> AgentState:
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
    
async def write_req_specs(state: AgentState) -> AgentState:

    try:
        oel_input = """
        1. Device Compatibility
        Must support smartphones (iOS and Android) and optionally tablets.
        Minimum device specifications: e.g., Android 8.0+ or iOS 14+.
        Support both portrait and landscape orientations.
        2. Operating System
        Android devices: Android 8.0 and above.
        iOS devices: iOS 14 and above.
        Ensure compatibility with upcoming OS updates for at least 2 years.
        3. Network Requirements
        Must work on Wi-Fi and mobile data (3G/4G/5G).
        Minimum bandwidth requirement for loading menus and images.
        Offline mode: Allow browsing of previously loaded menus when offline.
        4. Backend and APIs
        App connects to a backend server via RESTful APIs or GraphQL.
        Requires secure HTTPS connections.
        Supports load balancing for at least 10,000 simultaneous users.
        5. Browser Requirements (if web-based)
        Support latest versions of Chrome, Safari, Firefox, and Edge.
        Graceful degradation for unsupported browsers.
        6. Storage and Memory
        Local caching for offline use and performance optimization.
        Minimum RAM usage constraints for smooth operation.
        """

        # manually input OEL first
        oel_artifact = create_artifact(
            agent=AgentType.DEPLOYER,
            artifact_type=ArtifactType.OP_ENV_LIST,
            content=oel_input,  
        )

        # extract latest versions of OEL, SRL and RM
        latest_system_req = StateManager.get_latest_artifact_by_type(state, ArtifactType.SYSTEM_REQ)
        latest_req_model = StateManager.get_latest_artifact_by_type(state, ArtifactType.REQ_MODEL)

        system_req_content = await pydantic_to_json_text(latest_system_req.content)
        req_model_content = latest_req_model.content
        op_env_list_content = oel_artifact.content

        system_req_id = latest_system_req.id
        req_model_id = latest_req_model.id
        op_env_list_id = oel_artifact.id
    


        llm_with_structured_output = llm.with_structured_output(SoftwareRequirementSpecs)
        system_prompt = PROMPT_LIBRARY.get("write_req_specs")
        prompt_input = system_prompt.format(
            system_req_content=system_req_content, req_model_content=req_model_content, op_env_list_content=op_env_list_content, 
            system_req_id=system_req_id, req_model_id=req_model_id, op_env_list_id=op_env_list_id)

        if not system_prompt:
            raise ValueError("Missing 'write_req_specs' prompt in prompt library.")
        
        
        response = await llm_with_structured_output.ainvoke(
        [
            SystemMessage(content=prompt_input),
            HumanMessage(content=state.conversations[-1].content)
        ]
        )
        converted_text = await pydantic_to_json_text(response)


        # Create artifact using factory function
        artifact = create_artifact(
            agent=AgentType.ARCHIVIST,
            artifact_type=ArtifactType.SW_REQ_SPECS,
            content=response,  
        )
        
        # Create conversation entry
        conversation = create_conversation(
            agent=AgentType.ARCHIVIST,
            artifact_id=artifact.id,
            content=converted_text,
        )
        
        return {
            "artifacts": [artifact],  
            "conversations": [conversation],  
        }
        
    except Exception as e:
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }

async def verdict_to_revise_SRS(state: AgentState) -> str: 
    print("running this routing function")
    latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
    # if we still do not have validation report generated yet 
    if not latest_val_report: 
        print("True")
        return True
    else:
        try: 
            val_report_content = latest_val_report.content 
            val_report_id = latest_val_report.id
            latest_srs = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)    
            srs_content = latest_srs.content
            srs_id = latest_srs.id
            """
            Do some processing with the content 
            """
            system_prompt = PROMPT_LIBRARY.get("write_req_specs_with_val_rep")
            prompt_input = system_prompt.format(
                val_report_content=val_report_content, srs_content=srs_content, 
                srs_id=srs_id, val_report_id=val_report_id)
            
            if not system_prompt: 
                raise ValueError("Missing 'write_req_specs_with_val_rep' prompt in prompt library")
            
            response = await llm.invoke(
                [
                    SystemMessage(content=prompt_input), 
                    HumanMessage(content=state.conversations[-1].content)
                ]
            )  

            # if we need changes (after looking at validation report) 
            if response.strip().upper() == "YES": 
                print("True")
                return True
            
            elif response.strip().upper() == "NO": 
                print("False")
                return False 
            else: 
                raise Exception (f"LLM does not return True or False to revise SRS, it returns {response}")
        except Exception as e: 
            print(f"Error in verdict_to_revise_SRS: {e}")


async def revise_req_specs(state: AgentState) -> AgentState: 
    # 1. retrieve the latest version of validation report
    latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
    # not found 
    if not latest_val_report: 
        return None
    else: 
        try: 

            val_report_content = latest_val_report.content 
            val_report_id = latest_val_report.id
            latest_srs = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)    
            srs_content = latest_srs.content
            srs_id = latest_srs.id
            """
            Do some processing with the content 
            """
            system_prompt = PROMPT_LIBRARY.get("write_req_specs_with_val_rep")
            prompt_input = system_prompt.format(
                val_report_content=val_report_content, srs_content=srs_content, 
                srs_id=srs_id, val_report_id=val_report_id)
            
            if not system_prompt: 
                raise ValueError("Missing 'write_req_specs_with_val_rep' prompt in prompt library")

            llm_with_structured_output = llm.with_structured_output(SoftwareRequirementSpecs)
            response = await llm_with_structured_output.ainvoke(
                [
                    SystemMessage(content=prompt_input), 
                    HumanMessage(content=state.conversations[-1].content)
                ]
            )

            converted_text = await pydantic_to_json_text(response) 

            artifact = create_artifact(
                agent=AgentType.ARCHIVIST, 
                artifact_type=ArtifactType.SW_REQ_SPECS, 
                content=response,
            )

            conversation = create_conversation(
                agent=AgentType.ARCHIVIST, 
                artifact_id = artifact.id, 
                content=converted_text,
            )
            return {
                "artifacts": [artifact], 
                "conversations": [conversation],
            }
        except Exception as e: 
            return{
                "errors": [f"Classification failed: {str(e)}"]
            }
    
async def main():

    # Define a new graph
    workflow = StateGraph(AgentState)
    workflow.add_node("process_user_input", process_user_input)
    workflow.add_node("classify_user_requirements", classify_user_requirements)
    workflow.add_node("write_system_requirement", write_system_requirement)
    workflow.add_node("build_requirement_model", build_requirement_model)
    workflow.add_node("write_req_specs", write_req_specs)

    workflow.add_node("verdict_to_revise_SRS", verdict_to_revise_SRS)
    workflow.add_node("revise_req_specs", revise_req_specs)



    # Set the entrypoint as `agent`
    workflow.set_entry_point("process_user_input")
    workflow.add_edge("process_user_input", "classify_user_requirements")
    workflow.add_edge("classify_user_requirements", "write_system_requirement")
    workflow.add_edge("write_system_requirement", "build_requirement_model")
    workflow.add_edge("build_requirement_model", "write_req_specs")

    workflow.add_conditional_edges("write_req_specs", verdict_to_revise_SRS, {True: "revise_req_specs", False: END})
    workflow.add_edge("write_req_specs", END)

    async with AsyncSqliteSaver.from_conn_string("checkpoints.dc") as memory: 

        graph = workflow.compile()

        coro = graph.ainvoke({}, {"configurable": {"thread_id": "thread-1"}})

        print(await asyncio.gather(coro))

    
asyncio.run(main())


