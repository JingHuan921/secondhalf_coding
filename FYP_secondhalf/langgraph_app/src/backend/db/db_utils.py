import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

load_dotenv(override=True)

uri = os.getenv("MONGODB_URI")
client = MongoClient(uri)

SESSION_TO_THREAD_MAPPING = {}

# Use a single database for all threads
APP_DATABASE_NAME = "langgraph_app"

def save_session_thread_mapping(session_id: str, thread_id: str):
    """Saves the link between a user's session and a LangGraph thread."""
    print(f"DATABASE: Mapping session '{session_id}' to thread '{thread_id}'")
    SESSION_TO_THREAD_MAPPING[session_id] = thread_id

# the threads to and from DB are for interrutps!
def save_threadID_to_db(session_id: str, thread_id: str) -> None:
    db = client[APP_DATABASE_NAME]
    collection = db["thread_mappings"]

    # Upsert by replacing any existing document for this session
    thread_schema = {
        "_id": session_id,
        "thread_id": str(thread_id),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    collection.replace_one({"_id": session_id}, thread_schema, upsert=True)


# ==================== MongoDB Conversation & Artifact Storage ====================

def get_thread_db(thread_id: str):
    """Get the database for all app data (single database approach)."""
    # Note: thread_id is kept as parameter for backwards compatibility
    # but we now use a single database with thread_id as a document field
    return client[APP_DATABASE_NAME]


def save_artifact_to_db(thread_id: str, artifact_data: Dict[str, Any]) -> bool:
    """
    Save an artifact to MongoDB.

    Args:
        thread_id: The thread ID this artifact belongs to
        artifact_data: Dict containing artifact fields (id, content_type, content, etc.)

    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        db = client[APP_DATABASE_NAME]
        collection = db["artifacts"]

        # Prepare the document for MongoDB
        # Use composite _id with thread_id to ensure uniqueness across threads
        composite_id = f"{thread_id}_{artifact_data.get('artifact_id')}"
        artifact_doc = {
            "_id": composite_id,
            "artifact_id": artifact_data.get("artifact_id"),
            "artifact_type": artifact_data.get("artifact_type"),
            "agent": artifact_data.get("agent"),
            "content": artifact_data.get("content"),
            "version": artifact_data.get("version"),
            "timestamp": artifact_data.get("timestamp"),
            "node": artifact_data.get("node"),
            "thread_id": thread_id,
            "saved_at": datetime.now(timezone.utc).isoformat()
        }

        # Handle base64 data - MongoDB can store strings up to 16MB
        # If content contains base64 data, it's already in the content dict
        # No special handling needed unless you want to compress it

        # Use upsert to handle versioning - newer versions will update the document
        collection.replace_one(
            {"_id": composite_id},
            artifact_doc,
            upsert=True
        )

        logger.info(f"Saved artifact {artifact_doc['_id']} to MongoDB for thread {thread_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to save artifact to MongoDB: {str(e)}")
        return False


def save_conversation_to_db(thread_id: str, conversation_data: Dict[str, Any]) -> bool:
    """
    Save a conversation entry to MongoDB.

    Args:
        thread_id: The thread ID this conversation belongs to
        conversation_data: Dict containing conversation fields (content, agent, artifact_id, timestamp)

    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        db = client[APP_DATABASE_NAME]
        collection = db["conversations"]

        # Prepare the document for MongoDB
        conversation_doc = {
            "content": conversation_data.get("content"),
            "agent": conversation_data.get("agent"),
            "artifact_id": conversation_data.get("artifact_id"),
            "timestamp": conversation_data.get("timestamp"),
            "node": conversation_data.get("node"),
            "thread_id": thread_id,
            "saved_at": datetime.now(timezone.utc).isoformat()
        }

        # Insert the conversation (allow duplicates since conversations can have same content)
        collection.insert_one(conversation_doc)

        logger.info(f"Saved conversation to MongoDB for thread {thread_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to save conversation to MongoDB: {str(e)}")
        return False


def get_artifacts_from_db(thread_id: str, artifact_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve artifacts from MongoDB for a specific thread.

    Args:
        thread_id: The thread ID to retrieve artifacts for
        artifact_type: Optional filter by artifact type

    Returns:
        List of artifact documents sorted by timestamp (newest first)
    """
    try:
        db = client[APP_DATABASE_NAME]
        collection = db["artifacts"]

        query = {"thread_id": thread_id}
        if artifact_type:
            query["artifact_type"] = artifact_type

        # Sort by timestamp descending (newest first)
        artifacts = list(collection.find(query).sort("timestamp", -1))

        # Remove MongoDB's _id from the result for cleaner output
        for artifact in artifacts:
            artifact.pop("_id", None)

        logger.info(f"Retrieved {len(artifacts)} artifacts from MongoDB for thread {thread_id}")
        return artifacts

    except Exception as e:
        logger.error(f"Failed to retrieve artifacts from MongoDB: {str(e)}")
        return []


def get_conversations_from_db(thread_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve conversations from MongoDB for a specific thread.

    Args:
        thread_id: The thread ID to retrieve conversations for

    Returns:
        List of conversation documents sorted by timestamp (oldest first)
    """
    try:
        db = client[APP_DATABASE_NAME]
        collection = db["conversations"]

        # Sort by timestamp ascending (oldest first) to maintain chronological order
        conversations = list(collection.find({"thread_id": thread_id}).sort("timestamp", 1))

        # Remove MongoDB's _id from the result
        for conversation in conversations:
            conversation.pop("_id", None)

        logger.info(f"Retrieved {len(conversations)} conversations from MongoDB for thread {thread_id}")
        return conversations

    except Exception as e:
        logger.error(f"Failed to retrieve conversations from MongoDB: {str(e)}")
        return []


def get_latest_artifact_version(thread_id: str, artifact_type: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest version of a specific artifact type.

    Args:
        thread_id: The thread ID
        artifact_type: The type of artifact to retrieve

    Returns:
        The latest artifact document or None if not found
    """
    try:
        db = client[APP_DATABASE_NAME]
        collection = db["artifacts"]

        # Find all artifacts of this type and sort by version
        artifact = collection.find_one(
            {"thread_id": thread_id, "artifact_type": artifact_type},
            sort=[("timestamp", -1)]  # Get most recent by timestamp
        )

        if artifact:
            artifact.pop("_id", None)
            logger.info(f"Retrieved latest {artifact_type} artifact for thread {thread_id}")

        return artifact

    except Exception as e:
        logger.error(f"Failed to retrieve latest artifact from MongoDB: {str(e)}")
        return None


def delete_thread_data(thread_id: str) -> bool:
    """
    Delete all data for a specific thread.

    Args:
        thread_id: The thread ID to delete data for

    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        db = client[APP_DATABASE_NAME]

        # Delete all documents for this thread from all collections
        db["artifacts"].delete_many({"thread_id": thread_id})
        db["conversations"].delete_many({"thread_id": thread_id})

        logger.info(f"Deleted all data for thread {thread_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete thread data from MongoDB: {str(e)}")
        return False


def create_indexes():
    """
    Create indexes for better query performance.
    This should be called once at application startup.
    """
    try:
        db = client[APP_DATABASE_NAME]

        # Create indexes for artifacts
        artifacts_collection = db["artifacts"]
        artifacts_collection.create_index([("thread_id", ASCENDING), ("timestamp", -1)])
        artifacts_collection.create_index([("thread_id", ASCENDING), ("artifact_type", ASCENDING)])
        artifacts_collection.create_index([("timestamp", -1)])

        # Create indexes for conversations
        conversations_collection = db["conversations"]
        conversations_collection.create_index([("thread_id", ASCENDING), ("timestamp", ASCENDING)])
        conversations_collection.create_index([("artifact_id", ASCENDING)])

        # Create index for thread_mappings
        thread_mappings_collection = db["thread_mappings"]
        thread_mappings_collection.create_index([("thread_id", ASCENDING)])

        logger.info(f"Created indexes for {APP_DATABASE_NAME} database")

    except Exception as e:
        logger.error(f"Failed to create indexes: {str(e)}")
