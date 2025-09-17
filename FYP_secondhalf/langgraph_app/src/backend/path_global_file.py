from pathlib import Path

MOCK_LLM = False
SQLITE_DB = str(Path(__file__).parent / "checkpoints.sqlite")
DEBUG_MODE = False

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR =  BASE_DIR / "outputs"
PROMPT_DIR = BASE_DIR / "prompt_library"
PROMPT_DIR_DEPLOYER = BASE_DIR / "prompt_library/deployer_prompt.jsonl"
PROMPT_DIR_END_USER = BASE_DIR / "prompt_library/end_user_prompt.jsonl"
PROMPT_DIR_INTERVIEWER = BASE_DIR / "prompt_library/interviewer_prompt.jsonl"
PROMPT_DIR_ANALYST = BASE_DIR / "prompt_library/analyst_prompt.jsonl"