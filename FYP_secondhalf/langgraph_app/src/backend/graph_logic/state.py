from typing import Annotated, List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from backend.artifact_model import RequirementsClassificationList, SystemRequirementsList, RequirementsModel, SoftwareRequirementSpecs

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


# Domain Models
class ArtifactMetadata(BaseModel):
    """Metadata for artifacts"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0"
    last_modified_by: AgentType

class Artifact(BaseModel):
    """Response artifact for each workflow step"""
    id: str
    type: ArtifactType
    agent: AgentType
    content: Optional[Union[RequirementsClassificationList, SystemRequirementsList, RequirementsModel, SoftwareRequirementSpecs, str]] = None
    metadata: ArtifactMetadata

class Conversation(BaseModel):
    """Conversation entry linking agent responses to artifacts"""
    agent: Optional[AgentType] = None
    artifact_id: Optional [str] = None
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)




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
        same_type_artifacts = [a for a in result if a.type == new_artifact.type]
        
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
    return sorted(result, key=lambda a: a.metadata.created_at)

def _get_latest_version(artifacts: List[Artifact]) -> str:
    """
    Get the latest version number from a list of artifacts
    """
    if not artifacts:
        return "1.0"
    
    versions = []
    for artifact in artifacts:
        try:
            version_str = artifact.metadata.version
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
        return "1.1"

def _create_versioned_artifact(original_artifact: Artifact, new_version: str) -> Artifact:
    """
    Create a new artifact with updated version and timestamp
    """
    # Create new metadata with updated version and timestamp
    updated_metadata = ArtifactMetadata(
        created_at=datetime.utcnow(),  # New timestamp
        version=new_version,  # Updated version
        last_modified_by = original_artifact.agent

    )
    
    # Create new artifact with updated metadata but same content
    return Artifact(
        id=f"{original_artifact.type.value}_{original_artifact.agent.value}_v{new_version.replace('.', '-')}",  # Unique ID with version
        type=original_artifact.type,
        agent=original_artifact.agent,
        content=original_artifact.content,  # Same content, different version
        metadata=updated_metadata
    )

def add_conversations(existing: List[Conversation], new: List[Conversation]) -> List[Conversation]:
    """
    Add new conversations chronologically
    """
    if not new:
        return existing
    
    # Combine and sort by timestamp
    all_conversations = existing + new
    return sorted(all_conversations, key=lambda c: c.timestamp)

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


# Main AgentState with custom reducers
class AgentState(BaseModel):
    """
    Main agent state for requirements processing workflow
    """
    # for user input 
    input: Optional[str] = None

    # Core workflow data with custom reducers
    artifacts: Annotated[List[Artifact], add_artifacts] = Field(default_factory=list)
    conversations: Annotated[List[Conversation], add_conversations] = Field(default_factory=list)
    
    # Error handling
    errors: Annotated[List[str], update_error_log] = Field(default_factory=list)
    
    # Session info (no reducers - replacement behavior)
    session_id: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)


# Helper Functions for State Management
class StateManager:
    """Helper class for common state operations"""
    
    @staticmethod
    def get_latest_artifact_by_type(state: AgentState, artifact_type: ArtifactType) -> Optional[Artifact]:
        """Get the most recent artifact of a specific type (highest version)"""
        matching = [a for a in state.artifacts if a.type == artifact_type]
        if not matching:
            return None
        
        # Sort by version to get the latest
        return max(matching, key=lambda a: StateManager._parse_version(a.metadata.version))
    
    @staticmethod
    def get_artifact_by_id(state: AgentState, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID"""
        return next((a for a in state.artifacts if a.id == artifact_id), None)
    
    @staticmethod
    def get_all_versions_by_type(state: AgentState, artifact_type: ArtifactType) -> List[Artifact]:
        """Get all versions of artifacts of a specific type, sorted by version"""
        matching = [a for a in state.artifacts if a.type == artifact_type]
        return sorted(matching, key=lambda a: StateManager._parse_version(a.metadata.version))
    
    @staticmethod
    def get_conversations_by_artifact(state: AgentState, artifact_id: str) -> List[Conversation]:
        """Get all conversations related to a specific artifact"""
        return [c for c in state.conversations if c.artifact_id == artifact_id]
    
    @staticmethod
    def get_conversations_by_agent(state: AgentState, agent: AgentType) -> List[Conversation]:
        """Get all conversations from a specific agent"""
        return [c for c in state.conversations if c.agent == agent]
    
    @staticmethod
    def has_artifact_type(state: AgentState, artifact_type: ArtifactType) -> bool:
        """Check if state contains an artifact of specific type"""
        return any(a.type == artifact_type for a in state.artifacts)
    
    @staticmethod
    def create_artifact_id(agent: AgentType, artifact_type: ArtifactType, metadata: ArtifactMetadata = None) -> str:
        """Generate consistent artifact ID"""
        # Check if you're doing something like this:
        # return f"{artifact_type.value}_{agent.value}_{metadata.version}"
        
        # Make sure agent and artifact_type are actually enum instances, not strings
        try:
            agent_value = agent.value if hasattr(agent, 'value') else str(agent)
            type_value = artifact_type.value if hasattr(artifact_type, 'value') else str(artifact_type)
            return f"{type_value}_{agent_value}_{metadata.version}"
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
) -> Artifact:
    
    """Factory function to create artifacts with proper metadata"""
    timestamp = datetime.utcnow()

    metadata = ArtifactMetadata(
        created_at=timestamp,
        last_modified_by= agent,
    )
    artifact_id = StateManager.create_artifact_id(agent, artifact_type, metadata)
    
    return Artifact(
        id=artifact_id,
        type=artifact_type,
        agent=agent,
        content=content,
        metadata=metadata
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
