"""
Requirements: 
1. How to inject documents into it and let llm knows that the name matches it 
1. archivist: to include version of documents afterwards 
2. split into two cases for write_req_specs: with and without validation report 
     - test retrieving document (validation report) from artifact
"""


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


# 1. search the latest versions of each documents 
# 2. feed in document (turned into text) into prompt
# 3. check output


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

    latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
    # if we still do not have validation report generated yet 
    if not latest_val_report: 
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


async def revise_req_specs (state: AgentState) -> AgentState: 
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
        
workflow = StateGraph(AgentState)
workflow.add_node("write_req_specs", write_req_specs)
workflow.add_node("verdict_to_revise_SRS", verdict_to_revise_SRS)
workflow.add_node("revise_req_specs", revise_req_specs)

workflow.set_entry_point("write_req_specs")
workflow.add_edge()

