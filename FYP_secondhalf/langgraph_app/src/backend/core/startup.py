"""
- You need it to have proper initialising of the app 
- And shutting down of the app
- Proper conenction and disconnection between them

"""
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.graph_logic.flow import setup_state_graph
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.path_global_file import SQLITE_DB


shared_resources = {}
CONN_STRING= SQLITE_DB

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context for initializing and shutting down the KGMAF application.

    Responsibilities:
    - Initialize knowledge bases, DB connections, agents, etc.
    - Cleanly disconnect services on shutdown.
    
    - Here should manage ALL lifecycle open and close of the app and DB, 
        - So there shouldnt be a connection "async with aiosqlite.connect(CONN_STRING)" in another file"
    
    """
    global Global_graph  # ✅ This makes sure the global variable is updated

    print("--- Application starting up... ---")
    
    conn = await aiosqlite.connect(CONN_STRING)
    print(f"✔️ Database connection established to {CONN_STRING}")
    
 
    await setup_state_graph(conn)
    print("✔️ LangGraph application compiled successfully.")
    
    
    yield # Here you will 1 constant connection to DB throughtou the whole lifespan!!!
    
    print("--- Application shutting down... ---")
  
    await conn.close()
    print("✔️ Database connection closed.")
    