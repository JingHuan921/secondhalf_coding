from backend.path_global_file import PROMPT_DIR_ANALYST
from backend.utils.main_utils import load_prompts, generate_plantuml_local, extract_plantuml
from backend.artifact_model import RequirementsClassificationList, SystemRequirementsList, RequirementsModel

from langchain_core.tools import tool 
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode


import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import Optional, Union, List, Annotated
from operator import add


# This loads all key-value pairs from a .env file into os.environ
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")



# Load prompt library once
prompt_path = PROMPT_DIR_ANALYST
PROMPT_LIBRARY = load_prompts(prompt_path)



def add_final_response(
    existing: Optional[Union[
        List[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel]], 
        RequirementsClassificationList, 
        SystemRequirementsList, 
        RequirementsModel
    ]], 
    new: Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel, List[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel]]]
) -> List[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel]]:
    """
    Custom reducer function to add new responses to final_response list
    """
    # Handle case where existing is None
    if existing is None:
        existing_list = []
    # Handle case where existing is a single object (convert to list)
    elif isinstance(existing, (RequirementsClassificationList, SystemRequirementsList, RequirementsModel)):
        existing_list = [existing]
    # Handle case where existing is already a list
    elif isinstance(existing, list):
        existing_list = existing
    else:
        existing_list = []
    
    # Handle new value
    if isinstance(new, list):
        return existing_list + new
    else:
        return existing_list + [new]

class AgentState(MessagesState):
    # Final structured response from the agent with custom reducer
    final_response: Annotated[
        Optional[List[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel]]], 
        add_final_response
    ] = None



llm = init_chat_model("openai:gpt-4.1")


# Define the function that calls the model
def call_model(state: AgentState):
    response = llm.invoke(state["messages"])
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


async def classify_user_requirements (state: AgentState):
    llm_with_structured_output = llm.with_structured_output(RequirementsClassificationList)
    system_prompt = PROMPT_LIBRARY.get("classify_user_reqs")

    if not system_prompt:
        raise ValueError("Missing 'classify_user_reqs' prompt in prompt library.")


    response = await llm_with_structured_output.ainvoke(
    [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["messages"][-1].content)
    ]
    )
    return {"final_response": response}

async def write_system_requirement (state: AgentState):
    llm_with_structured_output = llm.with_structured_output(SystemRequirementsList)
    system_prompt = PROMPT_LIBRARY.get("write_system_req")

    if not system_prompt:
        raise ValueError("Missing 'write_system_req' prompt in prompt library.")

    response = await llm_with_structured_output.ainvoke(
    [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["messages"][-1].content)
    ]
    )
    return {"final_response": response}

async def generate_use_case_diagram(uml_code: str) -> str:
    """
    Generate a use case diagram from PlantUML code
    
    Args:
        uml_code: The PlantUML code to generate diagram from
        output_location: Optional base directory for output (defaults to script parent directory)
    
    Returns:
        Path to the generated diagram file or error message
    """
    try:
        result = await generate_plantuml_local(uml_code=uml_code)  # <-- await here
        if result:
            return f"Use case diagram generated successfully at: {result}"
        else:
            return "Failed to generate use case diagram. Check PlantUML installation and code syntax."
    except Exception as e:
        return f"Error generating diagram: {str(e)}"
    

async def build_requirement_model(state: AgentState):
    """
    Build requirement model, extract UML, generate diagram, and return UML chunk
    """
    system_prompt = PROMPT_LIBRARY.get("build_req_model")

    if not system_prompt:
        raise ValueError("Missing 'build_req_model' prompt in prompt library.")
    
    # Get the LLM response
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["messages"][-1].content)
    ])
    
    # Extract PlantUML code from the response
    uml_chunk = None
    diagram_generation_message = "No PlantUML code found in response."
    
    if hasattr(response, 'content') and response.content:
        try:
            # Extract the UML chunk using your existing function
            uml_chunk = extract_plantuml(response.content)
            
            # Generate the diagram using the tool
            diagram_result = await generate_use_case_diagram(
                uml_code = uml_chunk
            )
            diagram_generation_message = diagram_result
            
        except ValueError:
            # No PlantUML code found
            uml_chunk = None
            diagram_generation_message = "No PlantUML code found in the LLM response."
        except Exception as e:
            # Error during diagram generation
            diagram_generation_message = f"Error generating diagram: {str(e)}"
    
    # Create final response - return the UML chunk if found, otherwise original response
    if uml_chunk:
        # Return just the UML chunk as the final response
        final_response_content = uml_chunk
        print(f"Diagram generation: {diagram_generation_message}")  # Log the diagram result
    else:
        # If no UML found, return the original response
        final_response_content = response.content if hasattr(response, 'content') else str(response)
        print(f"No UML extracted: {diagram_generation_message}")
    
    # Create AIMessage with the final content
    final_response = AIMessage(content=final_response_content)
    
    return {"final_response": final_response}



# Define a new graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("classify_user_requirements", classify_user_requirements)
workflow.add_node("write_system_requirement", write_system_requirement)
workflow.add_node("build_requirement_model", build_requirement_model)


# Set the entrypoint as `agent`
workflow.set_entry_point("agent")
workflow.add_edge("agent", "classify_user_requirements")
workflow.add_edge("classify_user_requirements", "write_system_requirement")
workflow.add_edge("write_system_requirement", "build_requirement_model")
workflow.add_edge("build_requirement_model", END)
graph = workflow.compile()

if __name__ == "__main__":
    prompt = PROMPT_LIBRARY.get("classify_user_reqs")
    human_input = prompt
    
    answer = graph.invoke(input={"messages": [("human", human_input)]})["final_response"]
    print(answer.model_dump_json(indent=2))