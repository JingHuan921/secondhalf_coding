from typing import Annotated, List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState

from backend.artifact_model import (
    RequirementsClassificationList,
    SystemRequirementsList,
    RequirementsModel,
    SoftwareRequirementSpecs
)

class AgentType(Enum):
    DEPLOYER = "Deployer"
    ANALYST = "Analyst"
    ARCHIVIST = "Archivist"
    REVIEWER = "Reviewer"
    USER = "User"

class ArtifactType(str, Enum):
    #Deployer 
    OP_ENV_LIST = "operating_env_list"

    #Analyst
    REQ_CLASS = "requirements_classification"
    SYSTEM_REQ = "system_requirements"
    REQ_MODEL = "requirements_model"

    #Archivist 
    SW_REQ_SPECS = "software_requirement_specs"
    
    #Reviewer 
    REVIEW_DOC = "review_document"
    VAL_REPORT = "validation_report"


class Artifact(BaseModel):
    """Response artifact for each workflow step"""
    id: str
    content: Optional[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel, SoftwareRequirementSpecs, str]] = None
    content_type: ArtifactType
    content_nature: Optional[str] = None #no use, for the sake of integratig
    created_by: AgentType
    version: str = "1.0"
    #to add later

    thread_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp:datetime = Field(default_factory=datetime.utcnow)
    #for potential RAG 
    embedding_id: Optional[str] = None 

class Conversation(BaseModel):
    """Conversation entry linking agent responses to artifacts"""
    agent: Optional[AgentType] = None
    artifact_id: Optional [str] = None
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# User will input this to resume after interrupt
class ResumeInput(BaseModel):
    thread_id: str
    choice: str

class ContinueInput(BaseModel):
    thread_id: str
    message: str


class ChatInput(BaseModel):
    message: str


class ThreadInput(BaseModel):
    thread_id: str



# ==========================================
class StartRequest(BaseModel):
    human_request: str

class ResumeRequest(BaseModel):
    thread_id: str
    review_action: Literal["approved", "feedback"]
    human_comment: Optional[str] = None


# Run_status to indicate 
class InitialInput(BaseModel):
    thread_id: str
    human_request: str


class DraftReviewState(MessagesState):
    human_request: str
    human_comment: Optional[str]


class GraphResponse(BaseModel):
    thread_id: str
    run_status: Literal["finished", "user_feedback", "pending"]
    assistant_response: Optional[str] = None


# Custom Reducer Functions
def add_artifacts(existing: List[Artifact], new: List[Artifact]) -> List[Artifact]:
    """
    Add new artifacts with intelligent versioning:
    - If same type but different content: increment version and add both
    - If different type: always add
    - If completely new: add as version 1.0
    """
    if not new:
        return existing
    
    result = existing.copy()
    
    for new_artifact in new:
        # Find existing artifacts of the same type
        same_type_artifacts = [a for a in result if a.content_type == new_artifact.content_type]
        
        if not same_type_artifacts:
            # No existing artifacts of this type - add as-is
            result.append(new_artifact)
        else:
            # Same type but different content - create new version
            latest_version = _get_latest_version(same_type_artifacts)
            new_version = _increment_version(latest_version)
            
            # Create new artifact with incremented version
            updated_artifact = _create_versioned_artifact(new_artifact, new_version)
            result.append(updated_artifact)
    
    # Sort by type, then by version for consistent ordering
    return sorted(result, key=lambda a: a.timestamp)

def _get_latest_version(artifacts: List[Artifact]) -> str:
    """
    Get the latest version number from a list of artifacts
    """
    if not artifacts:
        return ""
    
    versions = []
    for artifact in artifacts:
        try:
            version_str = str(artifact.version)
            # Parse version string (e.g., "1.0", "2.1", "1.10")
            major, minor = map(int, version_str.split('.'))
            versions.append((major, minor))
        except (ValueError, AttributeError):
            # If version parsing fails, assume it's 1.0
            versions.append((1, 0))
    
    # Return the highest version as a string
    max_major, max_minor = max(versions)
    return f"{max_major}.{max_minor}"

def _increment_version(version_str: str) -> str:
    """
    Increment version number (increment minor version)
    """
    try:
        major, minor = map(int, version_str.split('.'))
        return f"{major}.{minor + 1}"
    except (ValueError, AttributeError):
        # If parsing fails, return 1.1
        print("Error: Couldn't increment version, likely couldn't parse or find the current version well")
        return "1.1"

def _create_versioned_artifact(original_artifact: Artifact, new_version: str) -> Artifact:
    """
    Create a new artifact with updated version and timestamp
    """
    # Create new metadata with updated version and timestamp
    
    
    # Create new artifact with updated metadata but same content
    return Artifact(
        id=f"{original_artifact.content_type.value}_{original_artifact.created_by.value}_v{new_version.replace('.', '-')}",  # Unique ID with version
        content_type=original_artifact.content_type,
        created_by=original_artifact.created_by,
        content=original_artifact.content,  # Same content, different version
    )

def add_conversations(existing: List[Conversation], new: List[Conversation]) -> List[Conversation]:
    if not new:
        return existing

    combined = existing + new
    seen = set()
    unique = []
    for c in combined:
        key = (c.artifact_id, c.timestamp)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return sorted(unique, key=lambda c: c.timestamp)


def update_context(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge context dictionaries with smart handling of different value types
    """
    if not new:
        return existing
    
    result = existing.copy()
    
    for key, new_value in new.items():
        if key in result:
            existing_value = result[key]
            
            # Handle list merging
            if isinstance(existing_value, list) and isinstance(new_value, list):
                result[key] = existing_value + new_value
            elif isinstance(existing_value, list) and not isinstance(new_value, list):
                result[key] = existing_value + [new_value]
            elif not isinstance(existing_value, list) and isinstance(new_value, list):
                result[key] = [existing_value] + new_value
            # Handle dict merging
            elif isinstance(existing_value, dict) and isinstance(new_value, dict):
                merged_dict = existing_value.copy()
                merged_dict.update(new_value)
                result[key] = merged_dict
            # Replace for other types
            else:
                result[key] = new_value
        else:
            result[key] = new_value
    
    return result


def update_error_log(existing: List[str], new: List[str]) -> List[str]:
    """
    Append new errors to error log with timestamp
    """
    if not new:
        return existing
    
    timestamp = datetime.utcnow().isoformat()
    timestamped_errors = [f"[{timestamp}] {error}" for error in new]
    return existing + timestamped_errors


# Main ArtifactState with custom reducers
class ArtifactState(BaseModel):
    """
    Main agent state for requirements processing workflow
    """
    # Core workflow data with custom reducers
    artifacts: Annotated[List[Artifact], add_artifacts] = Field(default_factory=list) 
    conversations: Annotated[List[Conversation], add_conversations] = Field(default_factory=list)
    # for user input 
    human_request: Optional[str] = None
    current_agent: AgentType = None
    #to add 

    current_node: Optional[str] = None
    next_routing_node: Optional[str] = None
    # Error handling
    errors: Annotated[List[str], update_error_log] = Field(default_factory=list)
    
    # Session info (behavior)
    started_at: datetime = Field(default_factory=datetime.utcnow)


# Helper Functions for State Management
class StateManager:
    """Helper class for common state operations"""
    
    @staticmethod
    def get_latest_artifact_by_type(state: ArtifactState, artifact_type: ArtifactType) -> Optional[Artifact]:
        """Get the most recent artifact of a specific type (highest version)"""
        matching = [a for a in state.artifacts if a.content_type == artifact_type]
        if not matching:
            return None
        
        # Sort by version to get the latest
        return max(matching, key=lambda a: StateManager._parse_version(str(a.version)))
    
    @staticmethod
    def get_artifact_by_id(state: ArtifactState, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID"""
        return next((a for a in state.artifacts if a.id == artifact_id), None)
    
    @staticmethod
    def get_all_versions_by_type(state: ArtifactState, artifact_type: ArtifactType) -> List[Artifact]:
        """Get all versions of artifacts of a specific type, sorted by version"""
        matching = [a for a in state.artifacts if a.content_type == artifact_type]
        return sorted(matching, key=lambda a: StateManager._parse_version(str(a.version)))
    
    @staticmethod
    def get_conversations_by_artifact(state: ArtifactState, artifact_id: str) -> List[Conversation]:
        """Get all conversations related to a specific artifact"""
        return [c for c in state.conversations if c.artifact_id == artifact_id]
    
    @staticmethod
    def get_conversations_by_agent(state: ArtifactState, agent: AgentType) -> List[Conversation]:
        """Get all conversations from a specific agent"""
        return [c for c in state.conversations if c.agent == agent]
    
    @staticmethod
    def has_artifact_type(state: ArtifactState, artifact_type: ArtifactType) -> bool:
        """Check if state contains an artifact of specific type"""
        return any(a.content_type == artifact_type for a in state.artifacts)
    
    @staticmethod
    def create_artifact_id(agent: AgentType, artifact_type: ArtifactType, version:str) -> str:
        """Generate consistent artifact ID"""
        # Check if you're doing something like this:
        # return f"{artifact_type.value}_{agent.value}_{version}"
        
        try:
            agent_value = agent.value if hasattr(agent, 'value') else str(agent)
            type_value = artifact_type.value if hasattr(artifact_type, 'value') else str(artifact_type)
            return f"{type_value}_{agent_value}_{version}"
        except AttributeError as e:
            logger.error(f"Error in create_artifact_id: agent={agent}, artifact_type={artifact_type}")
            raise
    
    @staticmethod
    def _parse_version(version_str: str) -> tuple:
        """Parse version string into comparable tuple"""
        try:
            major, minor = map(int, version_str.split('.'))
            return (major, minor)
        except (ValueError, AttributeError):
            return (1, 0)

# Factory Functions for Creating State Objects
def create_artifact(
    agent: AgentType,
    artifact_type: ArtifactType,
    content: Optional[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel, str]] = None,
    version: str= "1.0"
) -> Artifact:
    
    """Factory function to create artifacts with proper metadata"""
    timestamp = datetime.utcnow()

    artifact_id = StateManager.create_artifact_id(agent, artifact_type, version=version)
    
    return Artifact(
        id=artifact_id,
        content_type=artifact_type,
        created_by=agent,
        content=content,
    )

def create_conversation(
    agent: AgentType,
    artifact_id: str,
    content: str,
) -> Conversation:
    
    timestamp = datetime.utcnow()
        
    return Conversation(
        timestamp = timestamp,
        agent=agent,
        artifact_id=artifact_id,
        content=content,
    )
