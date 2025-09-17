import inspect
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Check the constructor signature
sig = inspect.signature(AsyncSqliteSaver.__init__)
print(f"AsyncSqliteSaver.__init__ signature: {sig}")