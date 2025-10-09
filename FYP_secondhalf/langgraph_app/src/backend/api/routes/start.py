# src/backend/api/route/start.py

import os
import sys
import json
import time
import uuid
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4
import logging 

logger = logging.getLogger(__name__)

# --- Path setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# --- FastAPI ---
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

# --- Pydantic ---
from pydantic import BaseModel, Field, ValidationError

# --- Project-specific imports ---
from backend.core.startup import shared_resources  # Key import
from backend.graph_logic.state import (
    ArtifactState,
    ResumeInput,
    ChatInput,
    ContinueInput,
    ThreadInput,
    Artifact,
    InitialInput,
    ResumeRequest,
    GraphResponse,
)
from backend.utils.main_utils import load_prompts
from backend.path_global_file import OUTPUT_DIR
from backend.db.db_utils import (
    save_artifact_to_db,
    save_conversation_to_db,
    create_indexes
)

# --- LangGraph / LangChain ---
from langgraph.graph import StateGraph, Graph
from langgraph.graph.graph import CompiledGraph
from langgraph.types import Command
from langchain.schema import HumanMessage, SystemMessage, AIMessage

router = APIRouter()
shared_resources_start = {}

# Track the threads with their configurations
run_configs = {}

# Enhanced Pydantic models for resume functionality
class ResumeType(str, Enum):
    FEEDBACK = "feedback"
    APPROVED = "approved" 
    ROUTING_CHOICE = "routing_choice"
    ARTIFACT_FEEDBACK = "artifact_feedback"  # NEW: For artifact accept/feedback

# Enhanced ResumeRequest model
class EnhancedResumeRequest(BaseModel):
    thread_id: str
    resume_type: Optional[ResumeType] = ResumeType.FEEDBACK  # Default to feedback for backward compatibility
    review_action: Optional[str] = None  # For feedback: "approved" or "feedback"
    human_comment: Optional[str] = None  # For feedback comments
    user_choice: Optional[str] = None    # For routing choices
    # NEW: Artifact feedback fields
    artifact_id: Optional[str] = None    # For artifact feedback
    artifact_action: Optional[str] = None  # "accept" or "feedback"
    artifact_feedback: Optional[str] = None  # Feedback text for artifacts

# Valid routing choices
VALID_ROUTING_CHOICES = {
    "classify_user_requirements",
    "write_system_requirement", 
    "build_requirement_model",
    "write_req_specs",
    "revise_req_specs", 
    "no"
}

# Valid artifact actions
VALID_ARTIFACT_ACTIONS = {"accept", "feedback"}


try:
    from backend.graph_logic.flow import process_artifact_feedback_direct
    print("SUCCESS: process_artifact_feedback_direct imported successfully")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
except Exception as e:
    print(f"OTHER IMPORT ERROR: {e}")


@router.get("/")
async def root():
    return {"message": "KGMAF API is running", "docs": "/docs"}

# Add health check to verify graph is available
@router.get("/health")
def health_check():
    """Check if all services are available"""
    
    health_status = {
        "status": "healthy",
        "services": {
            "graph": shared_resources.get('graph') is not None,
            "checkpointer": shared_resources.get('checkpointer') is not None,
            "db_connection": shared_resources.get('db_connection') is not None,
        },
        "shared_resources_count": len(shared_resources)
    }
    
    # If any service is down, return 503
    if not all(health_status["services"].values()):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "services": health_status["services"],
                "message": "Some services are not available"
            }
        )
    
    return health_status

@router.post("/graph/stream/create", response_model=GraphResponse)
def create_graph_streaming(request: InitialInput):
    print(f"DEBUG: Successfully received validated request: {request}")
    print(f"DEBUG: human_request: {request.human_request}")
    
    # Check if graph is available before creating thread
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        print("ERROR: Graph not initialized or not available")
        raise HTTPException(
            status_code=503, 
            detail="The graph application is not available or has not been initialized."
        )
    
    print(f"DEBUG: Graph is available: {shared_resources['graph'] is not None}")
    
    thread_id = str(uuid4())
    
    run_configs[thread_id] = {
        "type": "start",
        "human_request": request.human_request
    }
    
    try:
        response = GraphResponse(
            thread_id=thread_id,
            run_status="pending",
            assistant_response=None
        )
        print(f"DEBUG: Successfully created response: {response}")
        return response
    except ValidationError as e:
        print(f"DEBUG: Response validation error: {e.errors()}")
        raise HTTPException(status_code=500, detail=f"Response validation failed: {str(e)}")

# Enhanced resume endpoint that handles feedback, routing choices, and artifact feedback
@router.post("/graph/stream/resume", response_model=GraphResponse)
def resume_graph_streaming(request: EnhancedResumeRequest):
    thread_id = request.thread_id
    
    # Check if graph is available
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        raise HTTPException(
            status_code=503, 
            detail="The graph application is not available or has not been initialized."
        )
    
    # Handle enhanced resume request if it has the new fields
    resume_type = request.resume_type or ResumeType.FEEDBACK
    user_choice = request.user_choice or None
    artifact_id = request.artifact_id or None
    artifact_action = request.artifact_action or None
    
    print(f"DEBUG: Resuming graph for thread_id={thread_id}, type={resume_type}")
    
    # Handle different types of resume requests
    if resume_type == ResumeType.ARTIFACT_FEEDBACK or artifact_id:
        # Handle artifact feedback resumption
        if not artifact_id:
            raise HTTPException(
                status_code=400,
                detail="artifact_id is required for artifact_feedback resume type"
            )
            
        if not artifact_action or artifact_action not in VALID_ARTIFACT_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid artifact_action. Must be one of: {list(VALID_ARTIFACT_ACTIONS)}"
            )
        
        print(f"DEBUG: Processing artifact feedback: {artifact_action} for artifact {artifact_id}")
        
        # Store artifact feedback configuration
        run_configs[thread_id] = {
            "type": "artifact_feedback",
            "artifact_id": artifact_id,
            "artifact_action": artifact_action,
            "artifact_feedback": request.artifact_feedback,
            "resume_type": resume_type.value if isinstance(resume_type, ResumeType) else resume_type
        }
        
    elif resume_type == ResumeType.ROUTING_CHOICE or user_choice:
        # Handle routing choice interrupt resumption
        if not user_choice:
            raise HTTPException(
                status_code=400,
                detail="user_choice is required for routing_choice resume type"
            )
            
        if user_choice not in VALID_ROUTING_CHOICES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user_choice. Must be one of: {list(VALID_ROUTING_CHOICES)}"
            )
        
        print(f"DEBUG: Processing routing choice: {user_choice}")
        
        # Store routing choice configuration
        run_configs[thread_id] = {
            "type": "routing_choice",
            "user_choice": user_choice,
            "resume_type": resume_type.value if isinstance(resume_type, ResumeType) else resume_type
        }
        
    else:
        # Handle feedback resumption (original logic)
        if not request.review_action:
            # For backward compatibility, try to infer from other fields
            if hasattr(request, 'human_comment') and request.human_comment:
                request.review_action = "feedback"
            else:
                raise HTTPException(
                    status_code=400,
                    detail="review_action is required for feedback resume type"
                )
        
        print(f"DEBUG: Processing feedback resumption: {request.review_action}")
        
        # Store feedback configuration (original logic)
        run_configs[thread_id] = {
            "type": "resume",
            "review_action": request.review_action,
            "human_comment": request.human_comment,
            "resume_type": resume_type.value if isinstance(resume_type, ResumeType) else "feedback"
        }
    
    return GraphResponse(
        thread_id=thread_id,
        run_status="pending",
        assistant_response=None
    )

feedback_nodes = []

# Map nodes to their corresponding agents for better UX
node_to_agent_map = {
    "process_user_input": "User",
    "classify_user_requirements": "Analyst", 
    "write_system_requirement": "Analyst",
    "build_requirement_model": "Analyst", 
    "write_req_specs": "Archivist",
    "verdict_to_revise_SRS": "Archivist",
    "revise_req_specs": "Archivist",
    "handle_routing_decision": "Routing"  # Add the routing decision node
}

import asyncio
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

@router.get("/graph/stream/{thread_id}")
async def stream_graph(request: Request, thread_id: str):
    # Add immediate logging
    print(f"=== SSE REQUEST START for thread_id: {thread_id} ===")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request method: {request.method}")
    print(f"Request URL: {request.url}")
    
    # Check if graph is available
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        print("ERROR: Graph not available in shared_resources")
        raise HTTPException(
            status_code=503, 
            detail="The graph application is not available or has not been initialized."
        )
    
    # Check if thread exists
    if thread_id not in run_configs:
        print(f"ERROR: Thread {thread_id} not found in run_configs")
        print(f"Available threads: {list(run_configs.keys())}")
        raise HTTPException(status_code=404, detail="Thread not found")
    
    print(f"Thread found: {run_configs[thread_id]}")
    
    graph = shared_resources['graph']
    run_data = run_configs[thread_id]
    config = {"configurable": {"thread_id": thread_id}}
    
    # NEW: Thread ID consistency checks
    print(f"DEBUG: ===== THREAD ID CONSISTENCY CHECK =====")
    print(f"DEBUG: URL thread_id: '{thread_id}'")
    print(f"DEBUG: Config thread_id: '{config['configurable']['thread_id']}'")
    print(f"DEBUG: Run_data keys: {list(run_data.keys())}")
    
    # Check if run_data has its own thread_id
    if 'thread_id' in run_data:
        print(f"DEBUG: Run_data thread_id: '{run_data['thread_id']}'")
        if run_data['thread_id'] != thread_id:
            print(f"WARNING: Thread ID mismatch in run_data!")
    
    # Check current graph state for this thread
    try:
        current_state = await graph.aget_state(config)
        if current_state and current_state.values:
            state_artifacts = current_state.values.get('artifacts', [])
            print(f"DEBUG: Current graph state has {len(state_artifacts)} artifacts")
            for i, art in enumerate(state_artifacts):
                art_thread_id = getattr(art, 'thread_id', 'NO_THREAD_ID')
                print(f"DEBUG: State artifact {i}: ID='{art.id}', thread_id='{art_thread_id}'")
                if art_thread_id != thread_id:
                    print(f"WARNING: Artifact {art.id} has different thread_id!")
        else:
            print(f"DEBUG: No current state found for thread {thread_id}")
    except Exception as e:
        print(f"ERROR: Failed to get current state: {e}")
    
    print(f"DEBUG: ===== END CONSISTENCY CHECK =====")

    async def event_generator():
        try:
            print("=== STARTING EVENT GENERATOR ===")

            # Create indexes for this thread (idempotent operation)
            create_indexes(thread_id)

            # Send initial ping to test connection
            initial_payload = json.dumps({
                "status": "connected",
                "thread_id": thread_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            print(f"Sending initial payload: {initial_payload}")
            yield initial_payload

            # Small delay to ensure connection is established
            await asyncio.sleep(0.1)
           
            input_state = None
            should_cleanup_thread = True  # Flag to control thread cleanup
            
            # Initialize event_type of different types of events
            if run_data["type"] == "start":
                event_type = "start"
                input_state = {"human_request": run_data["human_request"]}
            
            elif run_data["type"] == "routing_choice":
                event_type = "resume_routing"
                user_choice = run_data.get("user_choice")
                print(f"DEBUG: ===== ROUTING CHOICE FLOW =====")
                print(f"DEBUG: Resuming with routing choice: {user_choice}")

                # Check state BEFORE updating
                pre_routing_state = await graph.aget_state(config)
                print(f"DEBUG: BEFORE routing - state.next = {pre_routing_state.next}")

                updated_values = {
                    "next_routing_node": user_choice,
                    "human_request": user_choice
                }
                print(f"DEBUG: Updating state with: {updated_values}")
                await graph.aupdate_state(config, updated_values)

                # Check state AFTER updating
                post_routing_state = await graph.aget_state(config)
                print(f"DEBUG: AFTER routing - state.next = {post_routing_state.next}")
                print(f"DEBUG: AFTER routing - next_routing_node = {post_routing_state.values.get('next_routing_node', 'None')}")

                input_state = None
                print(f"DEBUG: Set input_state = None to continue from checkpoint")
                
            elif run_data["type"] == "artifact_feedback":
                event_type = "resume_artifact_feedback"
                
                # Handle artifact feedback processing
                artifact_id = run_data.get("artifact_id")
                artifact_action = run_data.get("artifact_action")
                artifact_feedback = run_data.get("artifact_feedback")
                
                print(f"DEBUG: Starting artifact feedback processing")
                print(f"DEBUG: artifact_id={artifact_id}")
                print(f"DEBUG: artifact_action={artifact_action}")
                print(f"DEBUG: artifact_feedback={artifact_feedback}")
                
                if artifact_action == "accept":
                    print(f"DEBUG: ===== ARTIFACT ACCEPTANCE FLOW =====")
                    print(f"DEBUG: Artifact {artifact_id} accepted, continuing workflow")

                    # Check state BEFORE updating
                    pre_accept_state = await graph.aget_state(config)
                    print(f"DEBUG: BEFORE acceptance - state.next = {pre_accept_state.next}")

                    # Send acceptance confirmation to frontend
                    acceptance_payload = json.dumps({
                        "chat_type": "conversation",
                        "content": f"✅ Artifact {artifact_id} has been accepted. Continuing with workflow...",
                        "node": "artifact_feedback_processor",
                        "agent": "System",
                        "artifact_id": artifact_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    yield acceptance_payload

                    # Clear ALL feedback-related state and set continuation flag
                    print(f"DEBUG: Updating state to clear feedback flags and set continuation flag...")
                    await graph.aupdate_state(config, {
                        "paused_for_feedback": False,
                        "artifact_feedback_id": None,
                        "artifact_feedback_action": None,
                        "artifact_feedback_text": None,
                        "continuing_after_feedback": True  # NEW: Flag to indicate continuation
                    })

                    # Check state AFTER updating
                    post_accept_state = await graph.aget_state(config)
                    print(f"DEBUG: AFTER state update - state.next = {post_accept_state.next}")
                    print(f"DEBUG: AFTER state update - continuing_after_feedback = {post_accept_state.values.get('continuing_after_feedback', False)}")

                    # CRITICAL: Check if artifact is from revise_req_specs and graph is at interrupt point
                    is_from_revise_req_specs = artifact_id.startswith("software_requirement_specs_")
                    is_at_interrupt = post_accept_state.next and 'handle_routing_decision' in post_accept_state.next

                    print(f"DEBUG: Artifact from revise_req_specs? {is_from_revise_req_specs}")
                    print(f"DEBUG: Graph at interrupt point? {is_at_interrupt}")

                    if is_from_revise_req_specs and is_at_interrupt:
                        print(f"DEBUG: Graph is ALREADY at interrupt point - sending interrupt notification")
                        print(f"DEBUG: NOT calling astream - waiting for user routing choice")

                        # Send interrupt notification to frontend
                        interrupt_payload = json.dumps({
                            "chat_type": "interrupt",
                            "status": "waiting_for_user_input",
                            "message": "Please choose the next action: classify_user_requirements, write_system_requirement, build_requirement_model, write_req_specs, revise_req_specs, or no",
                            "thread_id": thread_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        print(f"DEBUG: Sending interrupt payload to frontend: {interrupt_payload}")
                        yield interrupt_payload
                        print(f"DEBUG: Interrupt payload sent successfully")

                        # Keep thread alive for routing choice
                        should_cleanup_thread = False
                        print(f"DEBUG: Exiting event_generator, waiting for routing choice")
                        return  # Exit without streaming - graph is already interrupted
                    else:
                        print(f"DEBUG: Artifact not from revise_req_specs or no interrupt - continuing normally")
                        # CRITICAL: Set input_state to None to continue from checkpoint
                        input_state = None  # This tells LangGraph to continue from current state
                        print(f"DEBUG: Set input_state = None to continue from checkpoint")
                        # Fall through to graph streaming section
                    
                elif artifact_action == "feedback":
                    print(f"DEBUG: Processing feedback for artifact {artifact_id}")
                    
                    try:
                        # Get current state
                        current_state = await graph.aget_state(config)
                        print(f"DEBUG: Retrieved current state: {type(current_state)}")
                        print(f"DEBUG: State values keys: {list(current_state.values.keys()) if current_state.values else 'No values'}")
                        
                        # Send feedback processing notification
                        processing_payload = json.dumps({
                            "chat_type": "conversation",
                            "content": f"🔄 Processing your feedback for artifact {artifact_id}: '{artifact_feedback}'",
                            "node": "artifact_feedback_processor",
                            "agent": "System",
                            "artifact_id": artifact_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        yield processing_payload
                        
                        # Try to import the feedback processor
                        try:
                            from backend.graph_logic.flow import process_artifact_feedback_direct
                            print("DEBUG: Successfully imported process_artifact_feedback_direct")
                        except ImportError as e:
                            print(f"ERROR: Failed to import process_artifact_feedback_direct: {e}")
                            error_payload = json.dumps({
                                "chat_type": "error",
                                "content": f"Failed to import feedback processor: {str(e)}",
                                "node": "artifact_feedback_processor",
                                "agent": "System"
                            })
                            yield error_payload
                            return
                        
                        # Prepare feedback input
                        feedback_input = {
                            **current_state.values,
                            'artifact_feedback_id': artifact_id,
                            'artifact_feedback_action': artifact_action,
                            'artifact_feedback_text': artifact_feedback
                        }
                        
                        print(f"DEBUG: Calling process_artifact_feedback_direct with input keys: {list(feedback_input.keys())}")
                        
                        # IMPORTANT: Check if the function is async or sync
                        import inspect
                        if inspect.iscoroutinefunction(process_artifact_feedback_direct):
                            print("DEBUG: Function is async, calling with await")
                            feedback_result = await process_artifact_feedback_direct(feedback_input)
                        else:
                            print("DEBUG: Function is sync, calling directly")
                            feedback_result = process_artifact_feedback_direct(feedback_input)
                        
                        print(f"DEBUG: Feedback processing completed")
                        print(f"DEBUG: Result type: {type(feedback_result)}")
                        print(f"DEBUG: Result keys: {list(feedback_result.keys()) if feedback_result else 'No result'}")
                        
                        # DETAILED DEBUGGING: Print the actual content
                        if feedback_result:
                            for key, value in feedback_result.items():
                                print(f"DEBUG: {key} = {type(value)} with length {len(value) if hasattr(value, '__len__') else 'N/A'}")
                                if key == "conversations" and value:
                                    print(f"DEBUG: First conversation: {value[0] if value else 'None'}")
                                if key == "artifacts" and value:
                                    print(f"DEBUG: First artifact: {value[0].id if value else 'None'}")
                                # NEW: Print error details
                                if key == "errors" and value:
                                    print(f"DEBUG: Error content: {value}")
                                    for i, error in enumerate(value):
                                        print(f"DEBUG: Error {i}: {error}")
                        
                        # Check if there are errors and handle them
                        if feedback_result and feedback_result.get("errors"):
                            error_messages = feedback_result["errors"]
                            print(f"ERROR: process_artifact_feedback_direct returned errors: {error_messages}")
                            
                            # Send the actual errors to the frontend
                            for error_msg in error_messages:
                                error_payload = json.dumps({
                                    "chat_type": "error",
                                    "content": f"Feedback processing error: {error_msg}",
                                    "node": "artifact_feedback_processor",
                                    "agent": "System"
                                })
                                yield error_payload
                            
                            # Keep thread alive so user can try again
                            should_cleanup_thread = False
                            print(f"DEBUG: Keeping thread {thread_id} alive due to processing errors")
                            return
                        
                        # Check if the function actually processed the feedback successfully
                        if not feedback_result or (
                            not feedback_result.get("conversations") and 
                            not feedback_result.get("artifacts")
                        ):
                            print("ERROR: process_artifact_feedback_direct returned no conversations or artifacts")
                            error_payload = json.dumps({
                                "chat_type": "error",
                                "content": "The feedback processing function did not generate any revised artifacts. This might be a problem with the function implementation, or your feedback might need to be more specific.",
                                "node": "artifact_feedback_processor",
                                "agent": "System"
                            })
                            yield error_payload
                            
                            # Keep thread alive so user can try again
                            should_cleanup_thread = False
                            print(f"DEBUG: Keeping thread {thread_id} alive for retry")
                            return
                        
                        # Send conversation updates
                        if "conversations" in feedback_result and feedback_result["conversations"]:
                            print(f"DEBUG: Sending {len(feedback_result['conversations'])} conversation updates")
                            for conv in feedback_result["conversations"]:
                                conv_payload_dict = {
                                    "chat_type": "conversation",
                                    "content": conv.content,
                                    "node": "artifact_feedback_processor",
                                    "agent": conv.agent.value if hasattr(conv.agent, 'value') else str(conv.agent),
                                    "artifact_id": getattr(conv, 'artifact_id', None),
                                    "timestamp": conv.timestamp.isoformat() if hasattr(conv, 'timestamp') else datetime.now(timezone.utc).isoformat()
                                }
                                conv_payload = json.dumps(conv_payload_dict)
                                yield conv_payload

                                # Save conversation to MongoDB
                                save_conversation_to_db(thread_id, conv_payload_dict)
                        else:
                            print("DEBUG: No conversations in feedback result")
                        
                        # Send revised artifacts and require feedback again
                        if "artifacts" in feedback_result and feedback_result["artifacts"]:
                            print(f"DEBUG: Sending {len(feedback_result['artifacts'])} revised artifacts")
                            for art in feedback_result["artifacts"]:
                                print(f"DEBUG STREAM: Sending revised artifact {art.id}, version: {art.version}")

                                # Serialize content
                                content_data = None
                                if art.content:
                                    if hasattr(art.content, 'model_dump'):
                                        content_data = art.content.model_dump()
                                    else:
                                        content_data = str(art.content)

                                # Send the revised artifact
                                art_payload_dict = {
                                    "chat_type": "artifact",
                                    "artifact_id": art.id,
                                    "artifact_type": art.content_type.value if hasattr(art.content_type, 'value') else str(art.content_type),
                                    "agent": art.created_by.value if hasattr(art.created_by, 'value') else str(art.created_by),
                                    "content": content_data,
                                    "node": "artifact_feedback_processor",
                                    "version": art.version,
                                    "timestamp": art.timestamp.isoformat() if hasattr(art.timestamp, 'isoformat') else str(art.timestamp),
                                    "status": "completed"
                                }
                                art_payload = json.dumps(art_payload_dict)
                                yield art_payload

                                # Save artifact to MongoDB
                                save_artifact_to_db(thread_id, art_payload_dict)
                                
                                # Immediately require feedback for the revised artifact
                                print(f"DEBUG: Requiring feedback for revised artifact {art.id}")
                                feedback_required_payload = json.dumps({
                                    "chat_type": "artifact_feedback_required",
                                    "status": "artifact_feedback_required", 
                                    "pending_artifact_id": art.id,
                                    "thread_id": thread_id,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                })
                                yield feedback_required_payload
                        
                        # Update graph state with results
                        print(f"DEBUG: Updating graph state with feedback results")
                        await graph.aupdate_state(config, feedback_result)
                        
                        # Keep paused for the next feedback cycle
                        await graph.aupdate_state(config, {"paused_for_feedback": True})
                        
                        # DON'T delete the thread - we need it for the next feedback cycle
                        should_cleanup_thread = False
                        print(f"DEBUG: Keeping thread {thread_id} alive for next feedback cycle")
                        
                    except Exception as e:
                        print(f"ERROR: Failed to process artifact feedback: {str(e)}")
                        import traceback
                        print(f"ERROR: Full traceback: {traceback.format_exc()}")
                        
                        error_payload = json.dumps({
                            "chat_type": "error",
                            "content": f"Failed to process feedback: {str(e)}",
                            "node": "artifact_feedback_processor",
                            "agent": "System"
                        })
                        yield error_payload
                        
                        # Keep thread alive so user can try again
                        should_cleanup_thread = False
                        print(f"DEBUG: Keeping thread {thread_id} alive after exception")
                    
                    # Exit and wait for next user action (accept or more feedback)
                    return

                # For artifact acceptance, we DON'T return here - let the graph continue
                input_state = None
            else:
                # Original feedback resume logic
                event_type = "resume"
                state_update = {"status": run_data["review_action"]}
                if run_data.get("human_comment") is not None:
                    state_update["human_comment"] = run_data["human_comment"]
                await graph.aupdate_state(config, state_update)
                input_state = None

            # Send event type confirmation
            event_payload = json.dumps({
                "status": "processing", 
                "event_type": event_type,
                "thread_id": thread_id
            })
            print(f"Sending event type: {event_payload}")
            yield event_payload
            
            # Regular graph streaming - now includes continuation after artifact acceptance
            # After artifact acceptance, we need to continue the graph to reach any pending routing interrupts
            needs_graph_streaming = (
                run_data["type"] == "start" or
                run_data["type"] == "routing_choice" or
                (run_data["type"] == "artifact_feedback" and run_data.get("artifact_action") == "accept") or
                input_state is not None
            )
            
            print(f"DEBUG: needs_graph_streaming={needs_graph_streaming}, run_data type={run_data['type']}")
            
            if needs_graph_streaming:
                
                print(f"Starting graph streaming for continuation after artifact acceptance")
                
                # For artifact acceptance continuation, we need to resume the graph 
                # from where it was paused (None input means continue from current state)
                stream_input = input_state
                
                # Use stream_mode="updates" to get state changes after each node
                print(f"DEBUG: ===== STARTING astream LOOP =====")
                print(f"DEBUG: stream_input = {stream_input}")
                print(f"DEBUG: config = {config}")
                print(f"DEBUG: Checking state BEFORE astream...")
                pre_stream_state = await graph.aget_state(config)
                if pre_stream_state:
                    print(f"DEBUG: Pre-stream state.next = {pre_stream_state.next}")
                    print(f"DEBUG: Pre-stream state.values keys = {list(pre_stream_state.values.keys()) if pre_stream_state.values else 'None'}")
                    if pre_stream_state.values:
                        print(f"DEBUG: continuing_after_feedback = {pre_stream_state.values.get('continuing_after_feedback', False)}")
                        print(f"DEBUG: paused_for_feedback = {pre_stream_state.values.get('paused_for_feedback', False)}")
                        print(f"DEBUG: next_routing_node = {pre_stream_state.values.get('next_routing_node', 'None')}")

                node_count = 0
                async for state_update in graph.astream(stream_input, config, stream_mode="updates"):
                    node_count += 1
                    print(f"DEBUG: astream yielded update #{node_count}: {list(state_update.keys())}")

                    # CHECK FOR INTERRUPTS FIRST - this should now work after artifact acceptance
                    if "__interrupt__" in state_update:
                        print(f"DEBUG: Graph interrupted at thread_id={thread_id}")
                    
                        # Send interrupt status to frontend
                        interrupt_payload = json.dumps({
                            "chat_type": "interrupt",
                            "status": "waiting_for_user_input",
                            "message": "Please choose the next action: classify_user_requirements, write_system_requirement, build_requirement_model, write_req_specs, or revise_req_specs",
                            "thread_id": thread_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        yield interrupt_payload

                        # Store the current state for resumption
                        current_state = await graph.aget_state(config)
                        print(f"DEBUG: Stored interrupted state for thread_id={thread_id}")
                        
                        # DON'T delete the thread - we need it for resumption
                        should_cleanup_thread = False
                        # Exit the generator - frontend will need to make a new request to continue
                        return

                    for node_name, updates in state_update.items():
                        print(f"DEBUG: Node '{node_name}' completed with updates: {list(updates.keys())}")
                        
                        # NEW: Debug the actual state after node completion
                        print(f"DEBUG: Testing immediate state persistence after {node_name}...")
                        current_state_check = await graph.aget_state(config)
                        if current_state_check and current_state_check.values:
                            artifacts_in_state = current_state_check.values.get('artifacts', [])
                            conversations_in_state = current_state_check.values.get('conversations', [])
                            continuing_after_feedback = current_state_check.values.get('continuing_after_feedback', False)
                            print(f"DEBUG: After {node_name}, state now has {len(artifacts_in_state)} artifacts and {len(conversations_in_state)} conversations")
                            print(f"DEBUG: continuing_after_feedback flag: {continuing_after_feedback}")
                            
                            for i, art in enumerate(artifacts_in_state):
                                print(f"  Artifact {i}: {art.id} (thread: {getattr(art, 'thread_id', 'NO_THREAD')})")
                        else:
                            print(f"DEBUG: CRITICAL - After {node_name}, state is empty or has no values!")
                        
                        # This is for node routing before reaching END node
                        if "next_routing_node" in updates:
                            routing_payload = json.dumps({
                                "chat_type": "routing_decision",
                                "content": f"Routing to: {updates['next_routing_node']}",
                                "node": node_name,
                                "agent": node_to_agent_map.get(node_name, "Assistant"),
                                "next_node": updates["next_routing_node"],
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            yield routing_payload

                        # Handle new conversations - only from this node's update
                        # IMPORTANT: Routing nodes return full state, which includes accumulated conversations
                        # We need to skip those since routing nodes don't produce new conversations
                        # (routing messages are sent via routing_decision payload instead)
                        if node_name == "handle_routing_decision":
                            new_conversations = []
                            print(f"DEBUG: Skipping accumulated conversations for routing node '{node_name}'")
                        else:
                            new_conversations = updates.get("conversations", [])
                            print(f"DEBUG: Node {node_name} returned {len(new_conversations)} new conversations from its update")

                        # Only send conversations that were actually returned by this node
                        # (not the accumulated state conversations)
                        for conversation in new_conversations:
                            conversation_payload_dict = {
                                "chat_type": "conversation",
                                "content": conversation.content,
                                "node": node_name,
                                "agent": conversation.agent.value,
                                "artifact_id": conversation.artifact_id,
                                "timestamp": conversation.timestamp.isoformat()
                            }
                            conversation_payload = json.dumps(conversation_payload_dict)
                            yield conversation_payload

                            # Save conversation to MongoDB
                            save_conversation_to_db(thread_id, conversation_payload_dict)

                        # MODIFIED: Handle new artifacts with continuation logic
                        # Skip artifact processing for routing nodes
                        if node_name == "handle_routing_decision":
                            print(f"DEBUG: Skipping artifact processing for routing node '{node_name}'")
                        else:
                            new_artifacts = updates.get("artifacts", [])
                            print(f"DEBUG: Node {node_name} returned {len(new_artifacts)} new artifacts")
                            for artifact in new_artifacts:
                                print(f"DEBUG: Processing artifact from node update: {artifact.id} (thread: {getattr(artifact, 'thread_id', 'NO_THREAD')})")

                                # Serialize Pydantic model content properly
                                content_data = None
                                if artifact.content:
                                    if hasattr(artifact.content, 'model_dump'):  # Pydantic v2
                                        content_data = artifact.content.model_dump()
                                    else:
                                        content_data = str(artifact.content)  # Fallback for strings

                                artifact_payload_dict = {
                                    "chat_type": "artifact",
                                    "artifact_id": artifact.id,
                                    "artifact_type": artifact.content_type.value,
                                    "agent": artifact.created_by.value if hasattr(artifact.created_by, 'value') else str(artifact.created_by),
                                    "content": content_data,  # Now properly serialized
                                    "node": node_name,
                                    "version": artifact.version,
                                    "timestamp": artifact.timestamp.isoformat(),  # Use artifact's own timestamp
                                    "status": "completed"
                                }
                                artifact_payload = json.dumps(artifact_payload_dict)
                                yield artifact_payload

                                # Save artifact to MongoDB
                                save_artifact_to_db(thread_id, artifact_payload_dict)

                                # CRITICAL CHANGE: Check if we're continuing after feedback acceptance
                                current_state = await graph.aget_state(config)
                                continuing_after_feedback = current_state.values.get("continuing_after_feedback", False)

                                if artifact.id and artifact.content:
                                    if not continuing_after_feedback:
                                        # This is a NEW artifact - require feedback and exit
                                        print(f"DEBUG: NEW artifact {artifact.id} (version {artifact.version}) completed, requiring feedback")

                                        # CRITICAL DEBUG: Check state right before requiring feedback
                                        final_state_check = await graph.aget_state(config)
                                        if final_state_check and final_state_check.values:
                                            final_artifacts = final_state_check.values.get('artifacts', [])
                                            print(f"DEBUG: FINAL CHECK - State has {len(final_artifacts)} artifacts before requiring feedback")
                                            for i, art in enumerate(final_artifacts):
                                                print(f"  Final artifact {i}: {art.id} (thread: {getattr(art, 'thread_id', 'NO_THREAD')})")
                                        else:
                                            print(f"DEBUG: CRITICAL ERROR - Final state check shows empty state before requiring feedback!")

                                        # Send artifact feedback requirement
                                        feedback_required_payload = json.dumps({
                                            "chat_type": "artifact_feedback_required",
                                            "status": "artifact_feedback_required",
                                            "pending_artifact_id": artifact.id,
                                            "thread_id": thread_id,
                                            "timestamp": datetime.now(timezone.utc).isoformat()
                                        })
                                        yield feedback_required_payload

                                        # Store the current graph state to prevent race conditions
                                        await graph.aupdate_state(config, {"paused_for_feedback": True})

                                        # DON'T delete the thread - we need it for feedback
                                        should_cleanup_thread = False
                                        # Exit the generator - frontend will need to provide feedback
                                        return
                                    else:
                                        # We're continuing after feedback acceptance - don't require feedback again
                                        print(f"DEBUG: Continuing after feedback acceptance for artifact {artifact.id}, NOT requiring feedback again")
                                        # Clear the continuation flag so future artifacts will require feedback
                                        await graph.aupdate_state(config, {"continuing_after_feedback": False})
                                        # Continue processing - let the graph flow to the routing interrupt

                        # Handle errors
                        new_errors = updates.get("errors", [])
                        for error in new_errors:
                            error_payload = json.dumps({
                                "chat_type": "error",
                                "content": error,
                                "node": node_name,
                                "agent": node_to_agent_map.get(node_name, "Assistant")
                            })
                            yield error_payload

                # # Check if graph is interrupted (not actually completed)
                # print(f"DEBUG: ===== ASTREAM LOOP COMPLETED =====")
                # print(f"DEBUG: Total nodes processed in loop: {node_count}")
                # print(f"DEBUG: Checking final state to detect interrupt...")
                # final_state = await graph.aget_state(config)

                # print(f"DEBUG: final_state type: {type(final_state)}")
                # print(f"DEBUG: final_state.next: {final_state.next}")
                # print(f"DEBUG: final_state.values keys: {list(final_state.values.keys()) if final_state.values else 'None'}")

                # if final_state.next:  # If there are pending next nodes, we're interrupted
                #     print(f"DEBUG: ✓ INTERRUPT DETECTED! Next nodes to execute: {final_state.next}")
                #     print(f"DEBUG: Graph is waiting at an interrupt point, not completed!")
                #     interrupt_payload = json.dumps({
                #         "chat_type": "interrupt",
                #         "status": "waiting_for_user_input",
                #         "message": "Please choose the next action: ...",
                #         "thread_id": thread_id,
                #         "timestamp": datetime.now(timezone.utc).isoformat()
                #     })
                #     yield interrupt_payload
                #     should_cleanup_thread = False
                #     print(f"DEBUG: Returning early from event_generator due to interrupt")
                #     return  # Don't send completion
                # else:
                #     print(f"DEBUG: ✗ NO INTERRUPT - final_state.next is empty/None")
                #     print(f"DEBUG: Graph has completed normally, sending completion message")

                # Final completion message - use "finished" to distinguish from artifact "completed"
                print(f"DEBUG: Sending 'finished' status for thread {thread_id}")
                completion_payload = json.dumps({
                    "status": "finished",
                    "thread_id": thread_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                yield completion_payload
                print(f"DEBUG: 'finished' status sent successfully")

        except asyncio.CancelledError:
            print(f"Stream cancelled for thread {thread_id}")
            should_cleanup_thread = False  # Don't cleanup on cancellation
            raise
        except Exception as e:
            print(f"ERROR in event_generator: {str(e)}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            
            # Send error to frontend
            error_payload = json.dumps({
                "status": "error",
                "error": str(e),
                "thread_id": thread_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            yield error_payload
        finally:
            print(f"=== EVENT GENERATOR FINISHED for thread {thread_id} ===")
            # Only cleanup thread if we should (i.e., not waiting for feedback/routing)
            if should_cleanup_thread and thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs")
                del run_configs[thread_id]
            else:
                print(f"DEBUG: Keeping thread_id={thread_id} alive for future requests")

    # Return EventSourceResponse with proper headers
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )