from pathlib import Path 



# path to the file that stores prompt for different agents
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR =  BASE_DIR / "outputs"
PROMPT_DIR = BASE_DIR / "prompt_library"
PROMPT_DIR_ANALYST = BASE_DIR / "prompt_library/analyst_prompt.jsonl"
