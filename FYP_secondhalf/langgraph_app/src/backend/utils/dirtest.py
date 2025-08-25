
from pathlib import Path
# Add the src directory to Python path
current_file = Path(__file__).resolve()
util_dir = current_file.parent # Go up from src/backend/utils/ to src/

src_dir = current_file.parent.parent  # Go up from src/agent/ to src/
project_root = src_dir.parent         # Go up from src/ to langgraph_app/

# # Add both src and project root to Python path
# sys.path.insert(0, str(src_dir))
# sys.path.insert(0, str(project_root))