"""LangGraph graph for analyst agent deployment.

Imports and exposes the analyst graph for LangGraph Studio.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
# Add the src directory to Python path
current_file = Path(__file__).resolve()
src_dir = current_file.parent.parent  # Go up from src/agent/ to src/
project_root = src_dir.parent         # Go up from src/ to langgraph_app/

# Add both src and project root to Python path
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(project_root))

print(f"Current file: {current_file}")
print(f"Src directory: {src_dir}")
print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:3]}")

try:
    from langgraph.graph import StateGraph, MessagesState, END
    
    # Now try different import approaches for the analyst graph
    analyst_graph = None
    
    # Method 1: Direct import from backend
    try:
        from backend.agents.test_sqlitesaver import graph as analyst_graph
        print("Method 1: Imported analyst graph via 'from backend.agents.analyst'")
    except ImportError as e1:
        print(f"Method 1 failed: {e1}")
        
    
    # If we successfully imported the analyst graph, use it
    if analyst_graph is not None:
        graph = analyst_graph
        print("Successfully loaded analyst graph!")
    else:
        raise ImportError("All import methods failed")
        
except ImportError as e:
    print(f"Could not import analyst graph: {e}")
    print("Creating a simple test graph instead...")
    
    try:
        from langgraph.graph import StateGraph, MessagesState, END
        from langchain_core.messages import AIMessage
        
        # Create a simple test graph that works with MessagesState
        def simple_agent(state: MessagesState):
            """Simple agent that echoes back the input."""
            messages = state.get("messages", [])
            last_message = messages[-1] if messages else "No input"
            
            response_content = f"Test Echo: {last_message.content if hasattr(last_message, 'content') else str(last_message)}"
            
            return {"messages": [AIMessage(content=response_content)]}

        # Create the test graph
        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", simple_agent)
        workflow.set_entry_point("agent")
        workflow.add_edge("agent", END)
        
        graph = workflow.compile()
        print("Test graph created successfully")
        
    except Exception as fallback_error:
        print(f"Even fallback graph creation failed: {fallback_error}")
        graph = None