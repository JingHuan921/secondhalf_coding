# test_classifier.py
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate

# test_router_with_dummy_agents.py
from langgraph.graph import StateGraph, END
from typing import TypedDict


import os
from dotenv import load_dotenv


# This loads all key-value pairs from a .env file into os.environ
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")


llm = init_chat_model("openai:gpt-4.1")

class AgentState(TypedDict):
    user_input: str
    response: str

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

classifier_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a classifier. Decide which agent should handle the request.Prioritize Artifacts / Products mentioned over action keywords like 'Review', 'Refine'. For e.g., 'Review this RM' sounds like a Reviewer job, but prioritize RM which is actually in charge by analyst\n\n"
     + role_mapping +
     "\nRespond with only one word: 'analyst', 'archivist', or 'reviewer'."),
    ("user", "{text}")
])

classifier = classifier_prompt | llm

def router(state: AgentState):
    # Don't modify state here, just pass it through
    return state

def determine_route(state: AgentState):
    # This function determines which path to take
    role = classifier.invoke({"text": state["user_input"]}).content.strip().lower()
    return role

# Dummy agent functions
def analyst_agent(state: AgentState): 
    return {"response": f"[Analyst] Got: {state['user_input']}"}

def archivist_agent(state: AgentState): 
    return {"response": f"[Archivist] Got: {state['user_input']}"}

def reviewer_agent(state: AgentState): 
    return {"response": f"[Reviewer] Got: {state['user_input']}"}

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("analyst", analyst_agent)
workflow.add_node("archivist", archivist_agent)
workflow.add_node("reviewer", reviewer_agent)
workflow.add_node("router", router)

# Use conditional edges to route based on classification
workflow.add_conditional_edges(
    "router",
    determine_route,  # This function returns the role string
    {
        "analyst": "analyst",
        "archivist": "archivist", 
        "reviewer": "reviewer",
    },
)

workflow.set_entry_point("analyst")
workflow.add_edge("analyst", "archivist")
workflow.add_edge("archivist", "reviewer")
workflow.add_edge("reviewer", "router")
workflow.add_edge("reviewer", END)


graph = workflow.compile()

# # Run test
# tests = [
#     "Could you analyse this dataset?",
#     "Please archive the following record...",
#     "Hey reviewer, check this paragraph",
# ]

# for t in tests:
#     out = graph.invoke({"user_input": t})
#     print(f"Input: {t}\nOutput: {out['response']}\n")