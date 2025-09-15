from fastapi import Request, HTTPException
from langgraph.graph import Graph

# This is where your shared resources are stored by the lifespan manager
# We import it to create our dependency functions.
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.graph_logic.flow import shared_resources

def get_graph() -> Graph:
    """
    Dependency function that provides the compiled LangGraph instance.
    """
    graph = shared_resources.get("graph")
    if not graph:
        # This will happen if an endpoint is called before the lifespan startup is complete
        # or if startup failed.
        raise HTTPException(
            status_code=503, # 503 Service Unavailable
            detail="The graph application is not available or has not been initialized."
        )
    return graph

# You could also have a dependency for the DB connection if needed elsewhere,
# but it's often better to have dependencies provide higher-level objects like the graph.
if __name__ == "__main__":
    print(get_graph())