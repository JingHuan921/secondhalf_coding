

''''
    1. create actions as functions (can decorate as @tool) node wraps tool and call them internally (hybrid approach)
'''

from backend.path_global_file import PROMPT_DIR_ANALYST, MOCK_LLM, DEBUG_MODE
from backend.utils.main_utils import load_prompts


# Load prompt library once
prompt_path = PROMPT_DIR_ANALYST
PROMPT_LIBRARY = load_prompts(prompt_path)




async def classifyUserReqs(state: ArtifactState) -> str:
    """ Categorizes user requirements into functional and non-functional types and assigns priority levels using semantic labeling and classification
heuristics."""
    prompt_template = PROMPT_LIBRARY.get("end_interview_end_user")
    if not prompt_template:
        raise ValueError("Missing 'end_interview_end_user' prompt in prompt library.")

    # 1. Get formatted (speaker, message) lines
    conversation_history = get_conversation_str(state.conversations)

    # 2. Flatten to a string for the prompt
    
    prompt = prompt_template.format(conversation_history=conversation_history)
    # result = return_llm_output(prompt, conversation_history)
    if MOCK_LLM:
        result = "YES"
    else:
        result = await return_llm_output(prompt)
    
    if DEBUG_MODE:
        
        print(f"Output:\n{result}\n")
        print(state)

    print(f"Conversation History:\n{conversation_history}")
    return result