import sys
import os
import asyncio
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from backend.core.startup import shared_resources  # This is the key import
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
from backend.graph_logic.state import ArtifactState, ResumeInput, ChatInput, ContinueInput, ThreadInput, Artifact, InitialInput, ResumeRequest, GraphResponse
from backend.utils.main_utils import load_prompts
# Remove this import since we're not using the dependency anymore
# from backend.utils.dependencies import get_graph
from backend.path_global_file import OUTPUT_DIR
from langgraph.graph import StateGraph, Graph
from langgraph.types import Command
from langgraph.graph.graph import CompiledGraph
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse
import json
import time
import uuid
from enum import Enum

router = APIRouter()

shared_resources_start = {}

# Track the threads with their configurations
run_configs = {}

# Enhanced Pydantic models for resume functionality
class ResumeType(str, Enum):
    FEEDBACK = "feedback"
    APPROVED = "approved" 
    ROUTING_CHOICE = "routing_choice"

# Enhanced ResumeRequest model (you may need to update your existing model)
class EnhancedResumeRequest(BaseModel):
    thread_id: str
    resume_type: Optional[ResumeType] = ResumeType.FEEDBACK  # Default to feedback for backward compatibility
    review_action: Optional[str] = None  # For feedback: "approved" or "feedback"
    human_comment: Optional[str] = None  # For feedback comments
    user_choice: Optional[str] = None    # For routing choices

# Valid routing choices
VALID_ROUTING_CHOICES = {
    "classify_user_requirements",
    "write_system_requirement", 
    "build_requirement_model",
    "write_req_specs",
    "revise_req_specs"
}

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

# Enhanced resume endpoint that handles both feedback and routing choices
@router.post("/graph/stream/resume", response_model=GraphResponse)
def resume_graph_streaming(request: ResumeRequest):
    thread_id = request.thread_id
    
    # Check if graph is available
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        raise HTTPException(
            status_code=503, 
            detail="The graph application is not available or has not been initialized."
        )
    
    # Handle enhanced resume request if it has the new fields
    resume_type = getattr(request, 'resume_type', ResumeType.FEEDBACK)
    user_choice = getattr(request, 'user_choice', None)
    
    print(f"DEBUG: Resuming graph for thread_id={thread_id}, type={resume_type}")
    
    # Handle different types of resume requests
    if resume_type == ResumeType.ROUTING_CHOICE or user_choice:
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

# Alternative endpoint for direct routing choice handling (optional)
@router.post("/graph/resume/{thread_id}")
async def resume_interrupted_graph(thread_id: str, request_body: dict):
    """
    Resume an interrupted graph with user input.
    This endpoint specifically handles routing choice interrupts.
    """
    try:
        # Check if graph is available
        if 'graph' not in shared_resources or shared_resources['graph'] is None:
            raise HTTPException(
                status_code=503, 
                detail="The graph application is not available or has not been initialized."
            )
        
        user_choice = request_body.get("user_choice")
        if not user_choice:
            raise HTTPException(
                status_code=400,
                detail="user_choice is required"
            )
        
        # Validate user choice
        if user_choice not in VALID_ROUTING_CHOICES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid choice. Must be one of: {list(VALID_ROUTING_CHOICES)}"
            )
        
        print(f"DEBUG: Resuming interrupted graph for thread_id={thread_id} with choice: {user_choice}")
        
        # Get the current interrupted state
        graph = shared_resources['graph']
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await graph.aget_state(config)
        
        if not current_state.next:
            raise HTTPException(
                status_code=400,
                detail="No interrupted state found for this thread"
            )
        
        # Update the state with user input
        updated_values = {
            "next_routing_node": user_choice,
            "human_request": user_choice  # Store user input in human_request attribute
        }
        
        # Resume the graph with the updated state
        await graph.aupdate_state(config, updated_values)
        
        print(f"DEBUG: Graph state updated with user choice: {user_choice}")
        
        return {
            "status": "resumed",
            "user_choice": user_choice,
            "thread_id": thread_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error resuming graph: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
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
    "handle_routing_decision": "System"  # Add the routing decision node
}

# FIXED: Remove Depends(get_graph) and access graph from shared_resources
@router.get("/graph/stream/{thread_id}")
async def stream_graph(request: Request, thread_id: str):
    # Get graph from shared_resources instead of dependency injection
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        raise HTTPException(
            status_code=503, 
            detail="The graph application is not available or has not been initialized."
        )
    
    graph = shared_resources['graph']
    print(f"DEBUG: Using graph from shared_resources: {graph is not None}")

    if thread_id not in run_configs:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    run_data = run_configs[thread_id]
    config = {"configurable": {"thread_id": thread_id}}
    
    input_state = None
    
    # Handle different types of operations
    if run_data["type"] == "start":
        event_type = "start"
        input_state = {"human_request": run_data["human_request"]}
    elif run_data["type"] == "routing_choice":
        event_type = "resume_routing"
        # Handle routing choice resumption
        user_choice = run_data.get("user_choice")
        print(f"DEBUG: Resuming with routing choice: {user_choice}")
        
        # Update the graph state with the routing choice
        updated_values = {
            "next_routing_node": user_choice,
            "human_request": user_choice
        }
        await graph.aupdate_state(config, updated_values)
        input_state = None  # State already updated, continue from current state
    else:
        # Original feedback resume logic
        event_type = "resume"
        state_update = {"status": run_data["review_action"]}
        if run_data.get("human_comment") is not None:
            state_update["human_comment"] = run_data["human_comment"]
        await graph.aupdate_state(config, state_update)
        input_state = None

    async def event_generator():
        # Initial event with thread_id
        start_payload = json.dumps({"thread_id": thread_id})
        print(f"DEBUG: Sending initial {event_type} event with data: {start_payload}")
        yield start_payload

        try:
            print(f"DEBUG: Starting to stream graph updates for thread_id={thread_id}")
            
            # Use stream_mode="updates" to get state changes after each node
            async for state_update in graph.astream(input_state, config, stream_mode="updates"):
                print(f"DEBUG: Raw update: {state_update!r}")

                if "__interrupt__" in state_update:
                    print(f"DEBUG: Graph interrupted at thread_id={thread_id}")
                
                    # Send interrupt status to frontend
                    interrupt_payload = json.dumps({
                        "chat_type": "interrupt",
                        "status": "waiting_for_user_input",
                        "message": "Please choose the next action: classify_user_requirements, write_system_requirement, build_requirement_model, write_req_specs, or revise_req_specs",
                        "thread_id": thread_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    yield interrupt_payload

                    # Store the current state for resumption
                    current_state = await graph.aget_state(config)
                    print(f"DEBUG: Stored interrupted state for thread_id={thread_id}")
                    
                    # Exit the generator - frontend will need to make a new request to continue
                    return
                
                # Each state_update is like: { "node_name": { "conversations": [...], "artifacts": [...] } }
                for node_name, updates in state_update.items():
                    print(f"DEBUG: Node '{node_name}' completed with updates: {list(updates.keys())}")
                    
                    # Handle routing decision updates (next_routing_node changes)
                    if "next_routing_node" in updates:
                        routing_payload = json.dumps({
                            "chat_type": "routing_decision",
                            "content": f"Routing to: {updates['next_routing_node']}",
                            "node": node_name,
                            "agent": node_to_agent_map.get(node_name, "Assistant"),
                            "next_node": updates["next_routing_node"],
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        yield routing_payload

                    # Handle new conversations
                    new_conversations = updates.get("conversations", [])
                    for conversation in new_conversations:
                        conversation_payload = json.dumps({
                            "chat_type": "conversation",
                            "content": conversation.content,
                            "node": node_name,
                            "agent": node_to_agent_map.get(node_name, conversation.agent.value if conversation.agent else "Assistant"),
                            "artifact_id": conversation.artifact_id,
                            "timestamp": conversation.timestamp.isoformat()
                        })
                        yield conversation_payload

                    # Handle new artifacts
                    new_artifacts = updates.get("artifacts", [])
                    for artifact in new_artifacts:
                        artifact_payload = json.dumps({
                            "chat_type": "artifact",
                            "artifact_id": artifact.id,
                            "artifact_type": artifact.content_type.value,
                            "agent": node_to_agent_map.get(node_name, artifact.created_by.value),
                            "node": node_name,
                            "version": artifact.version,
                            "timestamp": artifact.timestamp.isoformat(),
                            "status": "completed"
                        })
                        yield artifact_payload

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

            # Check final state for feedback nodes
            final_state = await graph.aget_state(config)
            if final_state.next and any(node in final_state.next for node in feedback_nodes):
                status_data = json.dumps({"status": "user_feedback"})
                print(f"DEBUG: Sending status event (feedback): {status_data}")
                yield status_data
            else:
                status_data = json.dumps({"status": "finished"})
                print(f"DEBUG: Sending status event (finished): {status_data}")
                yield status_data

            # Cleanup
            if thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs")
                del run_configs[thread_id]

        except Exception as e:
            print(f"DEBUG: Exception in event_generator: {str(e)}")
            error_data = json.dumps({"error": str(e)})
            yield error_data
            if thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs after error")
                del run_configs[thread_id]

    return EventSourceResponse(event_generator())