# backend / graph_logic/flow.py
from typing import Any, Dict, List, Union, Optional, Annotated
import os
import json
import asyncio
from operator import add
from datetime import datetime, timezone
import logging
import sys
import base64

def setup_minimal_logging():
    """Setup minimal logging - suppress all LangGraph server noise"""
    
    # Configure basic logging first
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log', mode='w')
        ],
        force=True
    )
    
    # === SUPPRESS ALL LANGGRAPH SERVER LOGS ===
    logging.getLogger("langgraph_api").setLevel(logging.CRITICAL)
    logging.getLogger("langgraph_api.graph").setLevel(logging.CRITICAL)
    logging.getLogger("langgraph_runtime_inmem").setLevel(logging.CRITICAL)
    logging.getLogger("langgraph_runtime_inmem.queue").setLevel(logging.CRITICAL)
    logging.getLogger("langgraph.runtime").setLevel(logging.CRITICAL)
    logging.getLogger("langgraph.server").setLevel(logging.CRITICAL)
    
    # === SUPPRESS FILE WATCHER LOGS ===
    logging.getLogger("watchfiles").setLevel(logging.CRITICAL)
    logging.getLogger("watchfiles.main").setLevel(logging.CRITICAL)
    
    # === SUPPRESS OTHER NOISY SERVICES ===
    logging.getLogger("httpcore").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
    logging.getLogger("fastapi").setLevel(logging.CRITICAL)
    
    # === KEEP ONLY YOUR APPLICATION LOGS ===
    logging.getLogger("backend").setLevel(logging.DEBUG)  # Your app
    logging.getLogger("__main__").setLevel(logging.DEBUG)  # Main script
    
    # LangGraph core functionality (not server) - keep important messages only
    logging.getLogger("langgraph").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

setup_minimal_logging()
# Get your application logger
logger = logging.getLogger(__name__)

# Import langgraph AFTER setting up logging and environment variables
from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from langgraph.types import Command



from backend.path_global_file import PROMPT_DIR_ANALYST
from backend.utils.main_utils import (
    load_prompts, generate_plantuml_local, extract_plantuml, pydantic_to_json_text
)
from backend.graph_logic.state import (
    AgentType, ArtifactType, Artifact, Conversation, ArtifactState, StateManager,
    create_artifact, create_conversation, add_artifacts, add_conversations, 
     _get_latest_version, _increment_version, _create_versioned_artifact
)
from backend.artifact_model import RequirementsClassificationList, SystemRequirementsList, RequirementModel, SoftwareRequirementSpecs

from pydantic import BaseModel

from langchain_core.tools import tool 
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import ToolNode


import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from operator import add

# import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


# This loads all key-value pairs from a .env file into os.environ
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")



shared_resources = {}
graph = None


# Load prompt library once
prompt_path = PROMPT_DIR_ANALYST
PROMPT_LIBRARY = load_prompts(prompt_path)

# For artifact revision after receiving user feedback 
ARTIFACT_REGENERATION_MAP = {
    ArtifactType.REQ_CLASS: {
        "function": "classify_user_requirements",
        "prompt_key": "classify_user_reqs",
        "structured_output": RequirementsClassificationList,
        "agent": AgentType.ANALYST
    },
    ArtifactType.SYSTEM_REQ: {
        "function": "write_system_requirement", 
        "prompt_key": "write_system_req",
        "structured_output": SystemRequirementsList,
        "agent": AgentType.ANALYST
    },
    ArtifactType.REQ_MODEL: {
        "function": "build_requirement_model",
        "prompt_key": "build_req_model", 
        "structured_output": None,  # Special handling for diagrams
        "agent": AgentType.ANALYST
    },
    ArtifactType.SW_REQ_SPECS: {
        "function": "write_req_specs",
        "prompt_key": "write_req_specs",
        "structured_output": SoftwareRequirementSpecs,
        "agent": AgentType.ARCHIVIST
    }
}

llm = init_chat_model("openai:gpt-4.1")

# First node: Process user input and convert to conversation
def process_user_input(state: ArtifactState, config: dict) -> ArtifactState:
    """
    First node: Convert user input to conversation entry
    This is the entry point that processes the user input from LangGraph Studio
    """
    try:
        thread_id = config["configurable"]["thread_id"]
        print(f"DEBUG: process_user_input using thread_id: {thread_id}")
        
        # Check if there's user input
        if not state.human_request or state.human_request.strip() == "":
            return {
                "errors": ["No user input provided"],
            }
        
        user_input = state.human_request.strip()
        state.current_agent = AgentType.USER
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

async def classify_user_requirements(state: ArtifactState, config: dict) -> ArtifactState:
    try:
        thread_id = config["configurable"]["thread_id"]
        print(f"DEBUG: classify_user_requirements using thread_id: {thread_id}")
        print(f"DEBUG: Current state before processing has {len(state.artifacts)} existing artifacts")
        
        # Debug current state artifacts
        if state.artifacts:
            for i, existing_art in enumerate(state.artifacts):
                print(f"DEBUG: Existing artifact {i}: {existing_art.id} (thread: {getattr(existing_art, 'thread_id', 'NO_THREAD')})")
        
        llm_with_structured_output = llm.with_structured_output(RequirementsClassificationList)
        system_prompt = PROMPT_LIBRARY.get("classify_user_reqs")

        if not system_prompt:
            raise ValueError("Missing 'classify_user_reqs' prompt in prompt library.")
        
        print(f"DEBUG: About to call LLM for classification")
        response = await llm_with_structured_output.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state.conversations[-1].content)
        ]
        )
        print(f"DEBUG: LLM response received successfully")

        # Extract summary for conversation
        summary = response.summary
        print(f"DEBUG: Extracted summary: {summary}")

        # Create artifact content without summary using model_dump and exclude
        artifact_dict = response.model_dump(exclude={'summary'})
        artifact_content = RequirementsClassificationList(**artifact_dict)
        print(f"DEBUG: Created artifact content without summary")

        # Check for existing artifacts of same type and increment version
        latest_artifact = StateManager.get_latest_artifact_by_type(state, ArtifactType.REQ_CLASS)
        if latest_artifact:
            current_version = latest_artifact.version or "1.0"
            new_version = _increment_version(current_version)
            print(f"DEBUG: Found existing REQ_CLASS v{current_version}, creating v{new_version}")
        else:
            new_version = "1.0"
            print(f"DEBUG: No existing REQ_CLASS found, creating v{new_version}")

        artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.REQ_CLASS,
            content=artifact_content,
            version=new_version,
            thread_id=thread_id,

        )

        print(f"DEBUG: About to return artifact: {artifact.id} with thread_id: {artifact.thread_id}")
        print(f"DEBUG: Artifact content type: {artifact.content_type}")
        print(f"DEBUG: Artifact created by: {artifact.created_by}")

        # Create conversation entry using summary
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=artifact.id,
            content=summary
        )
        
        print(f"DEBUG: Conversation created with artifact_id: {conversation.artifact_id}")
        
        result = {
            "artifacts": [artifact],  
            "conversations": [conversation],  
        }
        
        print(f"DEBUG: Returning result with {len(result['artifacts'])} artifacts and {len(result['conversations'])} conversations")
        print(f"DEBUG: Result artifact IDs: {[art.id for art in result['artifacts']]}")
        
        return result
        
    except Exception as e:
        print(f"ERROR: Exception in classify_user_requirements: {str(e)}")
        import traceback
        print(f"ERROR: Full traceback: {traceback.format_exc()}")
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }
async def write_system_requirement(state: ArtifactState, config: dict) -> ArtifactState:
    try:
        thread_id = config["configurable"]["thread_id"]
        print(f"DEBUG: write_system_requirement using thread_id: {thread_id}")
        
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

        # Extract summary for conversation
        summary = response.summary

        # Create artifact content without summary using model_dump and exclude
        artifact_dict = response.model_dump(exclude={'summary'})
        artifact_content = SystemRequirementsList(**artifact_dict)

        # Check for existing artifacts of same type and increment version
        latest_artifact = StateManager.get_latest_artifact_by_type(state, ArtifactType.SYSTEM_REQ)
        if latest_artifact:
            current_version = latest_artifact.version or "1.0"
            new_version = _increment_version(current_version)
            print(f"DEBUG: Found existing SYSTEM_REQ v{current_version}, creating v{new_version}")
        else:
            new_version = "1.0"
            print(f"DEBUG: No existing SYSTEM_REQ found, creating v{new_version}")

        # Create artifact with explicit thread_id
        artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.SYSTEM_REQ,
            content=artifact_content,
            version=new_version,
            thread_id=thread_id,

        )
        # Create conversation entry using summary
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=artifact.id,
            content=summary
        )

        return {
            "artifacts": [artifact],  # Will be added via reducer
            "conversations": [conversation],  # Will be added via reducer
        }
        
    except Exception as e:
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }

async def generate_use_case_diagram(uml_code: str) -> dict:
    """
    Generate a use case diagram from PlantUML code and return both path and base64 data

    Args:
        uml_code: The PlantUML code to generate diagram from

    Returns:
        Dict containing path, base64_data, and success status
    """
    try:
        logger.debug(f"DEBUG: generate_use_case_diagram started")
        result = await generate_plantuml_local(uml_code=uml_code)
        
        if result:
            # Read the generated PNG file and convert to base64
            try:
                with open(result, 'rb') as image_file:
                    image_data = image_file.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    
                return {
                    "success": True,
                    "path": result,
                    "base64_data": base64_data,
                    "message": f"Use case diagram generated successfully at: {result}"
                }
            except Exception as e:
                logger.error(f"Error reading generated image: {str(e)}")
                return {
                    "success": False,
                    "path": result,
                    "base64_data": None,
                    "message": f"Diagram generated but failed to read image data: {str(e)}"
                }
        else:
            return {
                "success": False,
                "path": None,
                "base64_data": None,
                "message": "Failed to generate use case diagram. Check PlantUML installation and code syntax."
            }
            
    except Exception as e:
        return {
            "success": False,
            "path": None,
            "base64_data": None,
            "message": f"Error generating diagram: {str(e)}"
        }

async def build_requirement_model(state: ArtifactState, config: dict) -> ArtifactState:
    logger.debug("DEBUG: build_requirement_model function started")
    
    try:
        thread_id = config["configurable"]["thread_id"]
        print(f"DEBUG: build_requirement_model using thread_id: {thread_id}")
        
        logger.debug("DEBUG: Attempting to load 'build_req_model' prompt from library")
        system_prompt = PROMPT_LIBRARY.get("build_req_model")

        if not system_prompt:
            logger.debug("ERROR: Missing 'build_req_model' prompt in prompt library")
            raise ValueError("Missing 'build_req_model' prompt in prompt library.")
            
        # Get the LLM response
        logger.debug("DEBUG: Invoking LLM for requirement model generation")
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state.conversations[-1].content)
        ])
        logger.debug("DEBUG: LLM response received successfully")
        
        # Extract PlantUML code from the response
        uml_chunk = None
        diagram_result = None
        diagram_generation_message = "No PlantUML code found in response."
        
        if hasattr(response, 'content') and response.content:
            logger.debug("DEBUG: LLM response has content, attempting UML extraction")
            try:
                # Extract the UML chunk using your existing function
                logger.debug("DEBUG: Calling extract_plantuml function")
                uml_chunk = extract_plantuml(response.content)
                logger.debug(f"DEBUG: UML extraction successful, chunk length: {len(uml_chunk)}")
                
                # Generate the diagram using the tool
                logger.debug("DEBUG: Attempting to generate use case diagram")
                diagram_result = await generate_use_case_diagram(uml_code=uml_chunk)
                diagram_generation_message = diagram_result["message"]
                logger.debug(f"DEBUG: Diagram generation completed: {diagram_generation_message}")
                
            except ValueError as ve:
                # No PlantUML code found
                logger.debug(f"DEBUG: ValueError during UML extraction: {ve}")
                uml_chunk = None
                diagram_generation_message = "No PlantUML code found in the LLM response."
            except Exception as e:
                # Error during diagram generation
                logger.debug(f"DEBUG: Exception during UML processing: {str(e)}")
                diagram_generation_message = f"Error generating diagram: {str(e)}"
        else:
            logger.debug("DEBUG: LLM response has no content or content attribute missing")

        # Note: For RequirementModel, we don't use structured_output, so we create it manually
        # We'll generate a simple summary for the conversation
        summary = "Requirements model with use case diagram generated successfully."

        # Create artifact content based on whether diagram generation succeeded
        if diagram_result and diagram_result["success"] and diagram_result["base64_data"]:
            artifact_content = RequirementModel(
                diagram_base64 = diagram_result["base64_data"],
                diagram_path = diagram_result["path"],
                uml_fmt_content = uml_chunk,
                summary = summary  # Include summary here temporarily
            )
            logger.debug(f"DEBUG: Added base64 data to artifact content, length: {len(diagram_result['base64_data'])}")
        else:
            # Create artifact with no diagram if generation failed
            artifact_content = RequirementModel(
                diagram_base64 = None,
                diagram_path = None,
                uml_fmt_content = uml_chunk,
                summary = summary
            )
            logger.debug(f"DEBUG: Diagram generation failed, creating artifact without diagram")

        # Exclude summary from artifact content using model_dump and exclude
        artifact_dict = artifact_content.model_dump(exclude={'summary'})
        artifact_content_without_summary = RequirementModel(**artifact_dict)

        logger.debug("DEBUG: Creating artifact and conversation objects")

        # Check for existing artifacts of same type and increment version
        latest_artifact = StateManager.get_latest_artifact_by_type(state, ArtifactType.REQ_MODEL)
        if latest_artifact:
            current_version = latest_artifact.version or "1.0"
            new_version = _increment_version(current_version)
            logger.debug(f"DEBUG: Found existing REQ_MODEL v{current_version}, creating v{new_version}")
        else:
            new_version = "1.0"
            logger.debug(f"DEBUG: No existing REQ_MODEL found, creating v{new_version}")

        artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.REQ_MODEL,
            content=artifact_content_without_summary,
            version=new_version,
            thread_id=thread_id,

        )


        logger.debug(f"DEBUG: Artifact created with ID: {artifact.id}")

        # Create conversation entry using summary
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=artifact.id,
            content=summary,
        )
        logger.debug(f"DEBUG: Conversation entry created for artifact: {artifact.id}")

        logger.debug("DEBUG: build_requirement_model function completed successfully")
        return {
            "artifacts": [artifact],  
            "conversations": [conversation],  
        }
    
    except Exception as e:
        logger.debug(f"ERROR: Exception in build_requirement_model: {str(e)}")
        logger.debug(f"ERROR: Exception type: {type(e).__name__}")
        import traceback
        logger.debug(f"ERROR: Traceback: {traceback.format_exc()}")
        return {
            "errors": [f"Requirement model generation failed: {str(e)}"]
        }

async def write_req_specs(state: ArtifactState, config: dict) -> ArtifactState:
    logger.debug(f"DEBUG: Running write_req_specs")
    try:
        thread_id = config["configurable"]["thread_id"]
        print(f"DEBUG: write_req_specs using thread_id: {thread_id}")
        
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

        # manually input OEL first - create with explicit thread_id
        oel_artifact = Artifact(
            id="operating_env_list_Deployer_v1.0",
            content=oel_input,
            content_type=ArtifactType.OP_ENV_LIST,
            created_by=AgentType.DEPLOYER,
            version="1.0",
            thread_id=thread_id,  # EXPLICIT thread_id
            timestamp=datetime.now(timezone.utc)
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

        # Extract summary for conversation
        summary = response.summary

        # Create artifact content without summary using model_dump and exclude
        artifact_dict = response.model_dump(exclude={'summary'})
        artifact_content = SoftwareRequirementSpecs(**artifact_dict)

        # Check for existing artifacts of same type and increment version
        latest_artifact = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)
        if latest_artifact:
            current_version = latest_artifact.version or "1.0"
            new_version = _increment_version(current_version)
            print(f"DEBUG: Found existing SW_REQ_SPECS v{current_version}, creating v{new_version}")
        else:
            new_version = "1.0"
            print(f"DEBUG: No existing SW_REQ_SPECS found, creating v{new_version}")

        # Create artifact with explicit thread_id
        artifact = create_artifact(
            agent=AgentType.ARCHIVIST,
            artifact_type=ArtifactType.SW_REQ_SPECS,
            content=artifact_content,
            version=new_version,
            thread_id=thread_id,

        )

        # Create conversation entry using summary
        conversation = create_conversation(
            agent=AgentType.ARCHIVIST,
            artifact_id=artifact.id,
            content=summary,
        )

        return {
            "artifacts": [artifact],  
            "conversations": [conversation],  
        }
        
    except Exception as e:
        return {
            "errors": [f"Classification failed: {str(e)}"]
        }

async def verdict_to_revise_SRS(state: ArtifactState) -> str: 
    logger.debug("running this routing function")
    latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
    # if we still do not have validation report generated yet 
    if not latest_val_report: 
        logger.debug("True")
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
                logger.debug("True")
                return True
            
            elif response.strip().upper() == "NO": 
                logger.debug("False")
                return False 
            else: 
                raise Exception (f"LLM does not return True or False to revise SRS, it returns {response}")
        except Exception as e: 
            logger.debug(f"Error in verdict_to_revise_SRS: {e}")

async def revise_req_specs(state: ArtifactState, config: dict) -> ArtifactState:
    try:
        thread_id = config["configurable"]["thread_id"]
        print(f"DEBUG: revise_req_specs using thread_id: {thread_id}")
        
        # 1. retrieve the latest version of validation report
        latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
        
        if latest_val_report: 
            val_report_content = latest_val_report.content 
            val_report_id = latest_val_report.id
        else: 
            val_report_content = None
            val_report_id = None
        latest_srs = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)    
        srs_content = latest_srs.content
        srs_id = latest_srs.id
        
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

        # Extract summary for conversation
        summary = response.summary

        # Create artifact content without summary using model_dump and exclude
        artifact_dict = response.model_dump(exclude={'summary'})
        artifact_content = SoftwareRequirementSpecs(**artifact_dict)

        latest_srs = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)
        new_version = _increment_version(latest_srs.version)

        artifact = create_artifact(
            agent=AgentType.ARCHIVIST,
            artifact_type=ArtifactType.SW_REQ_SPECS,
            content=artifact_content,
            version=new_version,
            thread_id=thread_id,
        )

        conversation = create_conversation(
            agent=AgentType.ARCHIVIST,
            artifact_id = artifact.id,
            content=summary,
        )
        return {
            "artifacts": [artifact], 
            "conversations": [conversation],
        }
    except Exception as e: 
        return{
            "errors": [f"Classification failed: {str(e)}"]
        }

async def handle_routing_decision(state: ArtifactState, config: dict) -> ArtifactState:
    """
    Handle routing decision with user input from human_request.
    If no human_request is provided, this will cause an interrupt.
    """
    thread_id = config["configurable"]["thread_id"]
    print(f"DEBUG: handle_routing_decision using thread_id: {thread_id}")

    logger.debug("DEBUG: --- Handling routing decision ---")

    # Check if we have user input from the resumed state
    if hasattr(state, 'next_routing_node') and state.next_routing_node:
        user_choice = state.next_routing_node
        print(f"DEBUG: Using user choice from human_request: {user_choice}")

        # Validate the choice
        valid_choices = [
            "classify_user_requirements",
            "write_system_requirement",
            "build_requirement_model",
            "write_req_specs",
            "revise_req_specs",
            "no"
        ]

        if user_choice in valid_choices:
            state.next_routing_node = user_choice
            # Clear the human_request after processing
            state.human_request = None
            logger.debug(f"DEBUG: Set next_routing_node to: {user_choice}")
        else:
            logger.debug(f"DEBUG: Invalid user choice: {user_choice}, defaulting to no")
            state.next_routing_node = "no"  # Changed from build_requirement_model
    else:
        # This should trigger an interrupt since no user input is available
        logger.debug("DEBUG: No user input available, graph will be interrupted")
        # Don't set next_routing_node - let the interrupt happen
        pass

    return state

def execute_routing_decision(state: ArtifactState) -> str:
    return state.next_routing_node or 'no'


#----------------------------------------- Revision after feedback -------------------------------------------------

async def process_artifact_feedback_direct(state_dict: dict) -> dict:
    """
    Process artifact feedback directly without going through the workflow.
    This function operates on state dictionary and returns updates.
    """
    try:
        artifact_feedback_id = state_dict.get('artifact_feedback_id')
        artifact_feedback_action = state_dict.get('artifact_feedback_action')
        artifact_feedback_text = state_dict.get('artifact_feedback_text')
        
        if not artifact_feedback_id:
            return {"errors": ["No artifact feedback ID provided"]}
        
        if artifact_feedback_action == "accept":
            # Create acceptance confirmation
            conversation = create_conversation(
                agent=AgentType.SYSTEM,
                artifact_id=artifact_feedback_id,
                content=f"✅ Artifact {artifact_feedback_id} has been accepted by the user."
            )
            return {"conversations": [conversation]}
        
        elif artifact_feedback_action == "feedback":
            if not artifact_feedback_text:
                return {"errors": ["No feedback text provided"]}
            
            # Find the original artifact in state
            original_artifact = None
            artifacts = state_dict.get('artifacts', [])
            
            for artifact in artifacts:
                if artifact.id == artifact_feedback_id:
                    original_artifact = artifact
                    break
            
            if not original_artifact:
                return {"errors": [f"Original artifact {artifact_feedback_id} not found"]}
            
            # Generate improved version
            return await generate_improved_artifact_direct(
                original_artifact, 
                artifact_feedback_text,
                state_dict.get('conversations', [])[-1].content if state_dict.get('conversations') else ""
            )
        
        else:
            return {"errors": [f"Unknown artifact feedback action: {artifact_feedback_action}"]}
            
    except Exception as e:
        logger.error(f"Error processing artifact feedback: {str(e)}")
        return {"errors": [f"Failed to process artifact feedback: {str(e)}"]}

async def generate_improved_artifact_direct(original_artifact: Artifact, feedback_text: str, user_input: str) -> dict:
    """
    Generate improved artifact directly based on feedback using the appropriate generation logic.
    """
    try:
        artifact_type = original_artifact.content_type
        
        if artifact_type not in ARTIFACT_REGENERATION_MAP:
            return {"errors": [f"No regeneration logic for artifact type: {artifact_type}"]}
        
        regen_config = ARTIFACT_REGENERATION_MAP[artifact_type]
        
        # Get the appropriate system prompt
        system_prompt = PROMPT_LIBRARY.get(regen_config["prompt_key"])
        if not system_prompt:
            return {"errors": [f"Missing prompt '{regen_config['prompt_key']}' in prompt library"]}
        
        # Create feedback-enhanced prompt
        feedback_enhanced_prompt = f"""
{system_prompt}

IMPORTANT: The user has provided feedback on a previous version of this artifact. 
Please incorporate the following feedback to improve the output:

User Feedback: "{feedback_text}"

Original Artifact Content: {await pydantic_to_json_text(original_artifact.content) if hasattr(original_artifact.content, 'model_dump') else str(original_artifact.content)}

Please generate an improved version that addresses the user's feedback while maintaining the required structure and format.
"""
        
        # Generate improved artifact based on type
        if artifact_type == ArtifactType.REQ_MODEL:
            # Special handling for requirement models with diagrams
            return await regenerate_requirement_model_direct(
                feedback_enhanced_prompt, 
                user_input, 
                original_artifact
            )
        else:
            # Standard regeneration for other artifact types
            return await regenerate_standard_artifact_direct(
                feedback_enhanced_prompt,
                user_input,
                original_artifact,
                regen_config
            )
            
    except Exception as e:
        logger.error(f"Error regenerating artifact with feedback: {str(e)}")
        return {"errors": [f"Failed to regenerate artifact: {str(e)}"]}

async def regenerate_standard_artifact_direct(
    enhanced_prompt: str,
    user_input: str, 
    original_artifact: Artifact,
    regen_config: dict
) -> dict:
    """
    Regenerate standard artifacts (non-diagram) with feedback.
    """
    try:
        # Use structured output for standard artifacts
        llm_with_structured_output = llm.with_structured_output(regen_config["structured_output"])
        
        response = await llm_with_structured_output.ainvoke([
            SystemMessage(content=enhanced_prompt),
            HumanMessage(content=user_input)
        ])

        # Extract summary for conversation
        summary = response.summary

        # Create artifact content without summary using model_dump and exclude
        artifact_dict = response.model_dump(exclude={'summary'})
        artifact_content = regen_config["structured_output"](**artifact_dict)

        # Get version from original artifact and increment
        current_version = original_artifact.version or "1.0"
        new_version = _increment_version(current_version)
        logger.debug(f"DEBUG: The new version of regenerated standard artifact is {new_version}")

        new_artifact = create_artifact(
            agent=regen_config["agent"],
            artifact_type=original_artifact.content_type,
            content=artifact_content,
            version=new_version,
            thread_id=original_artifact.thread_id,
        )
        logger.debug(f"DEBUG REGEN: current version is {current_version}, new version is {new_version}")
        logger.debug(f"DEBUG REGEN: Created artifact with ID={new_artifact.id}, version={new_artifact.version}")



        # Create conversation entry using summary with feedback indicator
        conversation = create_conversation(
            agent=regen_config["agent"],
            artifact_id=new_artifact.id,
            content=f"🔄 Updated based on feedback: {summary}"
        )
        
        return {
            "artifacts": [new_artifact],
            "conversations": [conversation]
        }
        
    except Exception as e:
        raise Exception(f"Failed to regenerate standard artifact: {str(e)}")

async def regenerate_requirement_model_direct(
    enhanced_prompt: str,
    user_input: str,
    original_artifact: Artifact
) -> dict:
    """
    Regenerate requirement model with diagram based on feedback.
    """
    try:
        # Generate new response
        response = await llm.ainvoke([
            SystemMessage(content=enhanced_prompt),
            HumanMessage(content=user_input)
        ])
        
        # Extract and generate new diagram
        uml_chunk = None
        diagram_result = None

        if hasattr(response, 'content') and response.content:
            try:
                uml_chunk = extract_plantuml(response.content)
                diagram_result = await generate_use_case_diagram(uml_code=uml_chunk)
            except ValueError:
                uml_chunk = None
            except Exception as e:
                logger.error(f"Error generating diagram: {str(e)}")

        # Create summary for conversation
        summary = "🔄 Updated requirements model based on user feedback."

        # Create artifact content
        if diagram_result and diagram_result["success"] and diagram_result["base64_data"]:
            artifact_content = RequirementModel(
                diagram_base64=diagram_result["base64_data"],
                diagram_path=diagram_result["path"],
                uml_fmt_content=uml_chunk,
                summary=summary
            )
        else:
            artifact_content = RequirementModel(
                diagram_base64=None,
                diagram_path=None,
                uml_fmt_content=uml_chunk,
                summary=summary
            )

        # Exclude summary from artifact using model_dump and exclude
        artifact_dict = artifact_content.model_dump(exclude={'summary'})
        artifact_content_without_summary = RequirementModel(**artifact_dict)

        current_version = original_artifact.version if hasattr(original_artifact, 'version') else "1.0"
        new_version = _increment_version(current_version)
        logger.debug(f"DEBUG REGEN: current version is {current_version}, new version is {new_version}")

        new_artifact = create_artifact(
            agent=AgentType.ANALYST,
            artifact_type=ArtifactType.REQ_MODEL,
            content=artifact_content_without_summary,
            version=new_version,
            thread_id=original_artifact.thread_id,
        )
        logger.debug(f"DEBUG REGEN REQ_MODEL: Created artifact with ID={new_artifact.id}, version={new_artifact.version}")


        print(f"DEBUG FEEDBACK: Created requirement model {new_artifact.id}, version: {new_artifact.version}, thread_id: {new_artifact.thread_id}")

        # Create conversation entry using summary
        conversation = create_conversation(
            agent=AgentType.ANALYST,
            artifact_id=new_artifact.id,
            content=summary
        )
        
        return {
            "artifacts": [new_artifact],
            "conversations": [conversation]
        }
        
    except Exception as e:
        raise Exception(f"Failed to regenerate requirement model: {str(e)}")


async def setup_state_graph(checkpointer: AsyncSqliteSaver):
    """Create workflow with enhanced logging"""
    logger.info("Creating LangGraph workflow...")

    workflow = StateGraph(ArtifactState)

    # Add nodes with logging
    logger.debug("Adding workflow nodes...")
    workflow.add_node("process_user_input", process_user_input)
    workflow.add_node("classify_user_requirements", classify_user_requirements)
    workflow.add_node("write_system_requirement", write_system_requirement)
    workflow.add_node("build_requirement_model", build_requirement_model)
    workflow.add_node("write_req_specs", write_req_specs)
    workflow.add_node("verdict_to_revise_SRS", verdict_to_revise_SRS)
    workflow.add_node("revise_req_specs", revise_req_specs)


    workflow.add_node("handle_routing_decision", handle_routing_decision)

    # Set entry point and edges with logging
    logger.debug("Setting entry point and edges...")
    workflow.set_entry_point("process_user_input")
    workflow.add_edge("process_user_input", "classify_user_requirements")
    workflow.add_edge("classify_user_requirements", "write_system_requirement")
    workflow.add_edge("write_system_requirement", "build_requirement_model")
    workflow.add_edge("build_requirement_model", "write_req_specs")

    workflow.add_conditional_edges(
        "write_req_specs", 
        verdict_to_revise_SRS, 
        {True: "revise_req_specs", False: END}
    )
    workflow.add_edge("revise_req_specs", "handle_routing_decision")

    workflow.add_conditional_edges(
            "handle_routing_decision",
            execute_routing_decision,
            {
                "classify_user_requirements": "classify_user_requirements",
                "write_system_requirement": "write_system_requirement",
                "build_requirement_model": "build_requirement_model",
                "write_req_specs": "write_req_specs",
                "revise_req_specs": "revise_req_specs",
                "no": END,
            }
        )

    graph = workflow.compile(interrupt_before=["handle_routing_decision"], 
                             checkpointer=checkpointer)

    return graph