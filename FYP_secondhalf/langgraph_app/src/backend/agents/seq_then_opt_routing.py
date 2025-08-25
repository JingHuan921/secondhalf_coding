from typing import TypedDict, Literal
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

llm = init_chat_model("openai:gpt-4.1")

class AgentState(TypedDict):
    user_input: str
    response: str
    analyst_document: str
    archivist_document: str 
    reviewer_document: str
    phase: str  # "initial" or "routing"
    iteration_count: int

role_mapping = """
Valid outputs: 'analyst', 'archivist', 'reviewer'

Artifacts / Products:
- analyst: requirement classification list, system requirement list (SRL), requirement model (RM), use case diagram
- archivist: software requirements specifications (SRS)
- reviewer: Review Document (RD), Validation Report (VR)

Actions:
- analyst: Categorizes user requirements into functional and non-functional types and assigns priority levels. Produces a structured system requirement list (SRL). Extracts actors, use cases, system boundary and synthesizes them into a requirement model (RM) using a use-case diagram with PlantUML.
- archivist: Generates initial SRS and refines it in response to updates or review feedback.
- reviewer: Reviews the SRS, checks for consistency and quality, and consolidates results into a validation report.
"""

# Classifier for routing
classifier_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a classifier. Decide which agent should handle the request. "
     "Prioritize Artifacts / Products mentioned over action keywords like 'Review', 'Refine'. "
     "For e.g., 'Review this RM' sounds like a Reviewer job, but prioritize RM which is actually in charge by analyst\n\n"
     + role_mapping +
     "\nRespond with only one word: 'analyst', 'archivist', or 'reviewer'."),
    ("user", "{text}")
])

classifier = classifier_prompt | llm

# Decision prompt for agents to decide if they should update their artifacts
decision_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an {agent_type}. Another agent has made changes. "
     "Look at the current state and decide if you need to update your own artifact.\n\n"
     "Current artifacts:\n"
     "- Analyst document: {analyst_doc}\n"
     "- Archivist document: {archivist_doc}\n" 
     "- Reviewer document: {reviewer_doc}\n\n"
     "Recent change: {recent_change}\n\n"
     "Should you update your artifact? Respond with only 'yes' or 'no'."),
    ("user", "Should I update my {agent_type} artifact?")
])

def analyst_agent(state: AgentState) -> dict:
    """Analyst creates/updates requirement analysis artifacts"""
    current_doc = state.get("analyst_document", "")
    user_input = state["user_input"]
    phase = state.get("phase", "initial")
    
    if phase == "initial":
        # Initial creation
        new_doc = f"[Analyst - Initial] Requirement Analysis for: {user_input}\n"
        new_doc += "- Functional Requirements: [TBD]\n"
        new_doc += "- Non-functional Requirements: [TBD]\n" 
        new_doc += "- System Requirements List (SRL): [TBD]\n"
        new_doc += "- Requirement Model (RM): [TBD]\n"
        response = "[Analyst] Created initial requirement analysis"
    else:
        # Update based on new input
        new_doc = current_doc + f"\n[Analyst - Update] Additional analysis for: {user_input}\n"
        new_doc += "- Updated requirements based on new input\n"
        response = "[Analyst] Updated requirement analysis with new information"
    
    return {
        "analyst_document": new_doc,
        "response": response
    }

def archivist_agent(state: AgentState) -> dict:
    """Archivist creates/updates SRS documentation"""
    current_doc = state.get("archivist_document", "")
    user_input = state["user_input"]
    phase = state.get("phase", "initial")
    
    if phase == "initial":
        # Initial creation
        new_doc = f"[Archivist - Initial] Software Requirements Specification (SRS)\n"
        new_doc += f"Based on: {user_input}\n"
        new_doc += "1. Introduction: [TBD]\n"
        new_doc += "2. System Requirements: [TBD]\n"
        new_doc += "3. Functional Specifications: [TBD]\n"
        response = "[Archivist] Created initial SRS documentation"
    else:
        # Check if should update based on changes
        analyst_doc = state.get("analyst_document", "")
        
        decision_chain = decision_prompt | llm
        should_update = decision_chain.invoke({
            "agent_type": "archivist",
            "analyst_doc": analyst_doc,
            "archivist_doc": current_doc,
            "reviewer_doc": state.get("reviewer_document", ""),
            "recent_change": f"New user input: {user_input}"
        }).content.strip().lower()
        
        if should_update == "yes":
            new_doc = current_doc + f"\n[Archivist - Update] SRS updated based on changes\n"
            new_doc += f"- Incorporated new requirements from: {user_input}\n"
            response = "[Archivist] Updated SRS documentation"
        else:
            new_doc = current_doc
            response = "[Archivist] No updates needed to SRS"
    
    return {
        "archivist_document": new_doc,
        "response": response
    }

def reviewer_agent(state: AgentState) -> dict:
    """Reviewer creates/updates review documents and validation reports"""
    current_doc = state.get("reviewer_document", "")
    user_input = state["user_input"]
    phase = state.get("phase", "initial")
    
    if phase == "initial":
        # Initial creation
        new_doc = f"[Reviewer - Initial] Review Document (RD) and Validation Report (VR)\n"
        new_doc += f"Review of: {user_input}\n"
        new_doc += "Quality Check: [TBD]\n"
        new_doc += "Consistency Check: [TBD]\n"
        new_doc += "Validation Status: [TBD]\n"
        response = "[Reviewer] Created initial review and validation documents"
    else:
        # Check if should update based on changes
        analyst_doc = state.get("analyst_document", "")
        archivist_doc = state.get("archivist_document", "")
        
        decision_chain = decision_prompt | llm
        should_update = decision_chain.invoke({
            "agent_type": "reviewer", 
            "analyst_doc": analyst_doc,
            "archivist_doc": archivist_doc,
            "reviewer_doc": current_doc,
            "recent_change": f"New user input: {user_input}"
        }).content.strip().lower()
        
        if should_update == "yes":
            new_doc = current_doc + f"\n[Reviewer - Update] Review updated based on changes\n"
            new_doc += f"- Re-validated requirements after: {user_input}\n"
            response = "[Reviewer] Updated review and validation documents"
        else:
            new_doc = current_doc
            response = "[Reviewer] No updates needed to review documents"
    
    return {
        "reviewer_document": new_doc,
        "response": response
    }

def phase_transition(state: AgentState) -> dict:
    """Transition from initial phase to routing phase"""
    return {
        "phase": "routing",
        "response": "Initial workflow complete. Now routing based on user input."
    }

def router(state: AgentState) -> dict:
    """Router that classifies user input and prepares for routing"""
    return state

def determine_route(state: AgentState) -> Literal["analyst", "archivist", "reviewer", "end"]:
    """Determines which agent to route to based on user input"""
    # Check if we want to end (could add logic here)
    if "stop" in state["user_input"].lower() or "end" in state["user_input"].lower():
        return "end"
    
    role = classifier.invoke({"text": state["user_input"]}).content.strip().lower()
    
    # Validate the role
    if role in ["analyst", "archivist", "reviewer"]:
        return role
    else:
        return "analyst"  # Default fallback

def increment_counter(state: AgentState) -> dict:
    """Increment iteration counter"""
    return {"iteration_count": state.get("iteration_count", 0) + 1}

# Build the workflow graph
workflow = StateGraph(AgentState)

# Add all nodes
workflow.add_node("analyst", analyst_agent)
workflow.add_node("archivist", archivist_agent) 
workflow.add_node("reviewer", reviewer_agent)
workflow.add_node("phase_transition", phase_transition)
workflow.add_node("router", router)
workflow.add_node("increment", increment_counter)

# Initial sequential flow: analyst -> archivist -> reviewer -> phase_transition
workflow.set_entry_point("analyst")
workflow.add_edge("analyst", "archivist")
workflow.add_edge("archivist", "reviewer")
workflow.add_edge("reviewer", "phase_transition")

# After phase transition, go to router
workflow.add_edge("phase_transition", "router")

# Routing logic from router
workflow.add_conditional_edges(
    "router",
    determine_route,
    {
        "analyst": "increment",
        "archivist": "increment", 
        "reviewer": "increment",
        "end": END
    }
)

# After increment, go to the respective agent, then back to router
workflow.add_conditional_edges(
    "increment",
    lambda state: determine_route(state),
    {
        "analyst": "analyst",
        "archivist": "archivist",
        "reviewer": "reviewer", 
        "end": END
    }
)

# In routing phase, all agents go back to archivist and reviewer for potential updates
def route_after_analyst(state: AgentState) -> Literal["archivist", "router"]:
    """After analyst updates, go to archivist to check if it needs updates"""
    if state.get("phase") == "routing":
        return "archivist"
    return "router"

def route_after_archivist(state: AgentState) -> Literal["reviewer", "router"]:
    """After archivist, go to reviewer to check if it needs updates"""
    if state.get("phase") == "routing":
        return "reviewer"
    return "router"

# Replace the simple edges with conditional routing for the routing phase
workflow.add_conditional_edges(
    "analyst",
    route_after_analyst,
    {
        "archivist": "archivist",
        "router": "router"
    }
)

workflow.add_conditional_edges(
    "archivist", 
    route_after_archivist,
    {
        "reviewer": "reviewer",
        "router": "router"
    }
)

# Reviewer always goes back to router in routing phase
workflow.add_edge("reviewer", "router")

# Compile the graph
graph = workflow.compile()

# Test the workflow
def test_workflow():
    print("=== Testing Sequential then Routing Workflow ===\n")
    
    # Initial run - should go through all agents sequentially
    print("1. Initial sequential run:")
    result = graph.invoke({
        "user_input": "I need a system for user authentication and data management",
        "phase": "initial",
        "iteration_count": 0
    })
    
    print(f"Phase: {result.get('phase')}")
    print(f"Iterations: {result.get('iteration_count')}")
    print(f"Response: {result.get('response')}")
    print(f"\nAnalyst Doc:\n{result.get('analyst_document', 'None')}")
    print(f"\nArchivist Doc:\n{result.get('archivist_document', 'None')}")
    print(f"\nReviewer Doc:\n{result.get('reviewer_document', 'None')}")
    print("\n" + "="*60 + "\n")
    
    # Now test routing - add new requirement
    print("2. Adding new requirement (should route to analyst):")
    result = graph.invoke({
        **result,  # Continue with previous state
        "user_input": "Add API rate limiting requirements to the RM"
    })
    
    print(f"Iterations: {result.get('iteration_count')}")
    print(f"Response: {result.get('response')}")
    print(f"\nUpdated Analyst Doc:\n{result.get('analyst_document', 'None')}")
    print(f"\nUpdated Archivist Doc:\n{result.get('archivist_document', 'None')}")
    print(f"\nUpdated Reviewer Doc:\n{result.get('reviewer_document', 'None')}")
    print("\n" + "="*60 + "\n")
    
    # Test with SRS update
    print("3. SRS update request (should route to archivist):")
    result = graph.invoke({
        **result,
        "user_input": "Update the SRS with security requirements"
    })
    
    print(f"Iterations: {result.get('iteration_count')}")
    print(f"Response: {result.get('response')}")
    print(f"\nFinal Archivist Doc:\n{result.get('archivist_document', 'None')}")

if __name__ == "__main__":
    test_workflow()





#example usage 
# Initial run
result = graph.invoke({
    "user_input": "Create a user authentication system",
    "phase": "initial", 
    "iteration_count": 0
})

# Follow-up routing
result = graph.invoke({
    **result,  # Continue with previous state
    "user_input": "Add API rate limiting to the RM"  # Will route to analyst
})