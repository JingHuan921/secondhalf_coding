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
    """
    
    print(f"Looking for database at: {CONN_STRING}")
    print(f"File exists: {os.path.exists(CONN_STRING)}")
    
    # Check if directory exists
    db_dir = os.path.dirname(CONN_STRING)
    print(f"Directory exists: {os.path.exists(db_dir)}")
    print(f"Files in directory: {os.listdir(db_dir) if os.path.exists(db_dir) else 'Directory not found'}")

    global Global_graph

    print("--- Application starting up... ---")

    # ✅ DELETE ALL SQLITE-RELATED FILES (including WAL files)
    sqlite_files = [
        CONN_STRING,
        CONN_STRING + "-shm",
        CONN_STRING + "-wal",
        CONN_STRING + "-journal"
    ]
    
    for file_path in sqlite_files:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✔️ Deleted: {os.path.basename(file_path)}")
    
    conn = await aiosqlite.connect(CONN_STRING)
    # Set better connection settings to prevent corruption
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA synchronous = NORMAL;") 
    await conn.execute("PRAGMA foreign_keys = ON;")
    print(f"Database connection established to {CONN_STRING}")
    
    memory = AsyncSqliteSaver(conn)
    print("AsyncSqliteSaver initialized successfully")
    
    # Setup the graph with the checkpointer
    Global_graph = await setup_state_graph(memory)
    print("LangGraph application compiled successfully.")
    
    # Store resources for access elsewhere
    shared_resources['checkpointer'] = memory
    shared_resources['graph'] = Global_graph
    shared_resources['db_connection'] = conn
    
    yield  # Application runs here
    
    print("--- Application shutting down... ---")
    
    if hasattr(memory, 'aclose'):
        await memory.aclose()
    await conn.close()
    print("Database connections closed cleanly.")