import sys
import os
import asyncio
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

router = APIRouter()

shared_resources_start = {}

# Track the threads with their configurations
run_configs = {}

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

@router.post("/graph/stream/resume", response_model=GraphResponse)
def resume_graph_streaming(request: ResumeRequest):
    thread_id = request.thread_id
    
    # Check if graph is available
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        raise HTTPException(
            status_code=503, 
            detail="The graph application is not available or has not been initialized."
        )
    
    print(f"DEBUG: Resuming graph for thread_id={thread_id}")
    run_configs[thread_id] = {
        "type": "resume",
        "review_action": request.review_action,
        "human_comment": request.human_comment
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
    "revise_req_specs": "Archivist"
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
    if run_data["type"] == "start":
        event_type = "start"
        input_state = {"human_request": run_data["human_request"]}
    else:
        event_type = "resume"
        state_update = {"status": run_data["review_action"]}
        if run_data["human_comment"] is not None:
            state_update["human_comment"] = run_data["human_comment"]
        await graph.aupdate_state(config, state_update)

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
                
                # Each state_update is like: { "node_name": { "conversations": [...], "artifacts": [...] } }
                for node_name, updates in state_update.items():
                    print(f"DEBUG: Node '{node_name}' completed with updates: {list(updates.keys())}")
                    
                    # Handle new conversations
                    new_conversations = updates.get("conversations", [])
                    for conversation in new_conversations:
                        conversation_payload = json.dumps({
                            "chat_type": "conversation",
                            "content": conversation.content,
                            "node": node_name,
                            "agent": conversation.agent.value if conversation.agent else "Assistant",
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
                            "agent": artifact.created_by.value,
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
                            "agent": "Assistant"
                        })
                        yield error_payload

            # Not sure if this works for feedback nodes yet
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