import sys
import os
import asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from fastapi import APIRouter, HTTPException, Request, Body, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field # BaseModel is used for data validation or you want a simple data structure for input by the user. 
from typing import Optional
from uuid import uuid4 #To give a unique id for eaech session
from backend.graph_logic.state import ArtifactState, ResumeInput, ChatInput, ContinueInput, ThreadInput, Artifact, InitialInput, ResumeRequest, GraphResponse
from backend.utils.main_utils import load_prompts
# from backend.db.db_utils import delete_session_db, save_threadID_to_db, retrieve_threadID_from_db
from backend.utils.dependencies import get_graph
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

# Add this to main.py after your existing imports
@router.get("/")
async def root():
    return {"message": "KGMAF API is running", "docs": "/docs"}


@router.post("/graph/stream/create", response_model=GraphResponse)
def create_graph_streaming(request: InitialInput):
    # This will only run if validation passes
    print(f"DEBUG: Successfully received validated request: {request}")
    print(f"DEBUG: human_request: {request.human_request}")
    
    thread_id = str(uuid4())
    
    run_configs[thread_id] = {
        "type": "start",
        "human_request": request.human_request
    }
    
    # ValidationError could still occur here if GraphResponse validation fails
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

conversation_nodes = [
    "classify_user_reqs",
    "write_system_req",
    "build_req_model",
    "write_req_specs", 
    "verdict_to_revise_SRS", 
    "write_req_specs_with_val_rep",

]

@router.get("/graph/stream/{thread_id}")
async def stream_graph(request: Request, thread_id: str, graph: CompiledGraph = Depends(get_graph)):
    # Check if thread_id exists in our configurations
    if thread_id not in run_configs:
        return {"error": "Thread ID not found. You must first call /graph/stream/create or /graph/stream/resume"}
    
    # Get the stored configuration
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
        # Initial event with thread_id and status
        start_payload = json.dumps({"thread_id": thread_id, "chat_type": "artifact"})
        print(f"DEBUG: Sending initial {event_type} event with data: {start_payload}")
        yield start_payload  # Only yield the payload

        current_chat_type = None  # Will be "artifact" or "conversation" on first item

        try:
            print(f"DEBUG: Starting to stream graph messages for thread_id={thread_id}")
            async for msg, metadata in graph.astream(input_state, config, stream_mode="messages"):
                if await request.is_disconnected():
                    print("DEBUG: Client disconnected")
                    break

                # Heuristic: conversation if this node is in conversation_nodes, else artifact
                is_conversation = metadata.get("langgraph_node") in conversation_nodes
                next_type = "conversation" if is_conversation else "artifact"

                # Announce phase on first item or when the phase flips
                if current_chat_type != next_type:
                    current_chat_type = next_type
                    phase_payload = json.dumps({"chat_type": current_chat_type})
                    print(f"DEBUG: Phase -> {current_chat_type}")
                    yield phase_payload  # Only yield the payload

                # Emit the actual content, tagged with current chat_type
                if current_chat_type == "conversation":
                    token_payload = json.dumps({
                        "chat_type": "conversation",
                        "content": msg.content
                    })
                    yield token_payload  # Only yield the payload
                else:
                    # Artifact data (no content in the message for now, just metadata)
                    artifact_payload = json.dumps({
                        "chat_type": "artifact",
                        "node": metadata.get("langgraph_node"),
                        "status": "ready"  # Optional, to show that the artifact is ready
                    })
                    yield artifact_payload  # Only yield the payload

            # After streaming completes, check if human feedback is needed
            state = await graph.aget_state(config)
            if state.next and any(node in state.next for node in feedback_nodes):
                status_data = json.dumps({"status": "user_feedback"})
                print(f"DEBUG: Sending status event (feedback): {status_data}")
                yield status_data  # Only yield the payload
            else:
                status_data = json.dumps({"status": "finished"})
                print(f"DEBUG: Sending status event (finished): {status_data}")
                yield status_data  # Only yield the payload

            # Cleanup
            if thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs")
                del run_configs[thread_id]

        except Exception as e:
            print(f"DEBUG: Exception in event_generator: {str(e)}")
            error_data = json.dumps({"error": str(e)})
            yield error_data  # Only yield the payload
            if thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs after error")
                del run_configs[thread_id]

    return EventSourceResponse(event_generator())
