from typing import Any, Dict, List, Union, Optional, Annotated
import os
import json
import asyncio
from operator import add

from dotenv import load_dotenv

from pydantic import BaseModel

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain.chat_models import init_chat_model

from langgraph.graph import MessagesState, StateGraph, END
from langgraph.prebuilt import ToolNode

from backend.path_global_file import PROMPT_DIR_ANALYST
from backend.utils.main_utils import (
    load_prompts,
    generate_plantuml_local,
    extract_plantuml,
    pydantic_to_json_text,
)
from backend.artifact_model import (
    RequirementsClassificationList,
    SystemRequirementsList,
    RequirementsModel,
)


from backend.graph_logic.test_state import (
    AgentType, ArtifactType, ArtifactMetadata, Artifact, Conversation, AgentState, StateManager,
    create_artifact, create_conversation, add_artifacts, add_conversations, 
     _get_latest_version, _increment_version, _create_versioned_artifact
)



# This loads all key-value pairs from a .env file into os.environ
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")



# Load prompt library once
prompt_path = PROMPT_DIR_ANALYST
PROMPT_LIBRARY = load_prompts(prompt_path)




llm = init_chat_model("openai:gpt-4.1")


# First node: Process user input and convert to conversation
def process_user_input(state: AgentState) -> AgentState:
    """
    First node: Convert user input to conversation entry
    This is the entry point that processes the user input from LangGraph Studio
    """
    try:
        # Check if there's user input
        if not state.input or state.input.strip() == "":
            return {
                "errors": ["No user input provided"],
            }
        
        user_input = state.input.strip()
        
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
async def eg_classify_requirements(state: AgentState) -> AgentState:
    """Example node showing how to use the AgentState"""


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
            content=response,  # Add your RequirementsClassificationList here
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


# Define a new graph
workflow = StateGraph(AgentState)
workflow.add_node("process_user_input", process_user_input)
workflow.add_node("eg_classify_requirements", eg_classify_requirements)


# Set the entrypoint as `agent`
workflow.set_entry_point("process_user_input")
workflow.add_edge("process_user_input", "eg_classify_requirements")
workflow.add_edge("eg_classify_requirements", END)
graph = workflow.compile()


if __name__ == "__main__":
    prompt = PROMPT_LIBRARY.get("classify_user_reqs")
    human_input = prompt
    
    answer = graph.invoke(input={"messages": [("human", human_input)]})["final_response"]
    print(answer.model_dump_json(indent=2))

