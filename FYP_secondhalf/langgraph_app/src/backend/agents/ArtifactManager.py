# from typing import TypedDict, Dict, Any, List, Optional, Union
# from pydantic import BaseModel, Field
# from dataclasses import dataclass, field
# from datetime import datetime
# from enum import Enum

# # # Your existing Pydantic models
# # class RequirementCategory(str, Enum):
# #     FUNCTIONAL = "functional"
# #     NON_FUNCTIONAL = "non_functional"
# #     CONSTRAINT = "constraint"

# # class RequirementPriority(str, Enum):
# #     HIGH = "high"
# #     MEDIUM = "medium"
# #     LOW = "low"

# # class RequirementClassification(BaseModel):
# #     """Response to the user for each requirement"""
# #     requirement_id: str
# #     requirement_text: str
# #     category: RequirementCategory
# #     priority: RequirementPriority

# # class RequirementsClassificationList(BaseModel):
# #     """Respond to the user with classification for all requirement items"""
# #     req_class_id: List[RequirementClassification] = Field(alias="classifications")

# # # Additional Pydantic models for other artifacts
# # class SystemRequirement(BaseModel):
# #     id: str
# #     description: str
# #     source_classification_id: str
# #     acceptance_criteria: List[str]

# # class SystemRequirementsList(BaseModel):
# #     requirements: List[SystemRequirement]
# #     version: str
# #     last_updated: datetime

# # class UseCaseActor(BaseModel):
# #     name: str
# #     type: str  # primary, secondary, system
# #     description: str

# # class UseCase(BaseModel):
# #     id: str
# #     name: str
# #     actors: List[UseCaseActor]
# #     preconditions: List[str]
# #     postconditions: List[str]
# #     main_flow: List[str]

# # class RequirementModel(BaseModel):
# #     use_cases: List[UseCase]
# #     system_boundary: str
# #     plantuml_diagram: str

# class SRSDocument(BaseModel):
#     version: str
#     introduction: str
#     system_overview: str
#     requirements: List[SystemRequirement]
#     validation_status: str
#     last_reviewed_by: Optional[str] = None
#     review_feedback: Optional[str] = None

# class ValidationIssue(BaseModel):
#     issue_id: str
#     severity: str  # critical, major, minor
#     description: str
#     affected_requirement_ids: List[str]
#     recommendation: str

# class ValidationReport(BaseModel):
#     report_id: str
#     srs_version: str
#     validation_date: datetime
#     overall_quality_score: float
#     consistency_check_passed: bool
#     issues: List[ValidationIssue]
#     recommendations: List[str]

# class ReviewDocument(BaseModel):
#     review_id: str
#     reviewed_artifacts: List[str]  # IDs of reviewed artifacts
#     reviewer_comments: str
#     approval_status: str  # approved, needs_revision, rejected

# # Simplified artifact metadata
# @dataclass
# class ArtifactMetadata:
#     created_by: str
#     created_at: datetime
#     last_modified_by: str
#     last_modified_at: datetime
#     version: int
#     dependencies: List[str] = field(default_factory=list)  # other artifact IDs this depends on
#     tags: List[str] = field(default_factory=list)

# @dataclass
# class Artifact:
#     id: str
#     type: str  # The artifact type name
#     content: Union[BaseModel, str, Dict[str, Any]]  # Pydantic model, string, or dict
#     metadata: ArtifactMetadata
    
#     def to_dict(self) -> Dict[str, Any]:
#         """Convert artifact to dictionary for serialization"""
#         if isinstance(self.content, BaseModel):
#             # convert pydantic to dictionary
#             content_dict = self.content.model_dump()
#         else:
#             content_dict = self.content
            
#         return {
#             "id": self.id,
#             "type": self.type,
#             "content": content_dict,
#             "metadata": {
#                 "created_by": self.metadata.created_by,
#                 "created_at": self.timestamp.isoformat(),
#                 "last_modified_by": self.metadata.last_modified_by,
#                 "last_modified_at": self.metadata.last_modified_at.isoformat(),
#                 "version": self.version,
#                 "dependencies": self.metadata.dependencies,
#                 "tags": self.metadata.tags
#             }
#         }

# # Artifact registry for reference (no access control)
# ARTIFACT_TYPES = {
#     # Analyst artifacts
#     "requirement_classification": {
#         "owner": "analyst",
#         "pydantic_model": RequirementsClassificationList,
#         "description": "Classification of requirements into categories and priorities"
#     },
#     "system_requirements_list": {
#         "owner": "analyst", 
#         "pydantic_model": SystemRequirementsList,
#         "description": "Structured system requirements list derived from classifications"
#     },
#     "requirement_model": {
#         "owner": "analyst",
#         "pydantic_model": RequirementModel,
#         "description": "Use case diagram and requirement model"
#     },
    
#     # Archivist artifacts  
#     "srs_document": {
#         "owner": "archivist",
#         "pydantic_model": SRSDocument,
#         "description": "Software Requirements Specification document"
#     },
#     "technical_specifications": {
#         "owner": "archivist",
#         "pydantic_model": None,
#         "description": "Detailed technical specifications"
#     },
    
#     # Reviewer artifacts
#     "validation_report": {
#         "owner": "reviewer",
#         "pydantic_model": ValidationReport,
#         "description": "Validation report with quality assessment and issues"
#     },
#     "review_document": {
#         "owner": "reviewer",
#         "pydantic_model": ReviewDocument,
#         "description": "Review document with comments and approval status"
#     },
#     "quality_metrics": {
#         "owner": "reviewer",
#         "pydantic_model": None,
#         "description": "Quality metrics and KPIs"
#     }
# }

# class AgentState(TypedDict):
#     # Input/Output
#     user_input: str
#     response: str
    
#     # Control flow
#     phase: str
#     iteration_count: int
    
#     # Artifact storage - all agents can access all artifacts
#     artifacts: Dict[str, Artifact]
    
#     # Workflow tracking
#     execution_history: List[Dict[str, Any]]

# # Simplified artifact management
# class ArtifactManager:
#     @staticmethod
#     def create_artifact(
#         artifact_id: str,
#         artifact_type: str, 
#         content: Union[BaseModel, str, Dict[str, Any]],
#         created_by: str,
#         dependencies: List[str] = None
#     ) -> Artifact:
#         """Create a new artifact"""
#         metadata = ArtifactMetadata(
#             created_by=created_by,
#             created_at=datetime.now(),
#             last_modified_by=created_by,
#             last_modified_at=datetime.now(),
#             version=1,
#             dependencies=dependencies or [],
#             tags=[artifact_type, created_by]
#         )
        
#         return Artifact(
#             id=artifact_id,
#             type=artifact_type,
#             content=content,
#             metadata=metadata
#         )
    
#     @staticmethod
#     def update_artifact(
#         artifact: Artifact, 
#         new_content: Union[BaseModel, str, Dict[str, Any]], 
#         modified_by: str
#     ) -> Artifact:
#         """Update existing artifact"""
#         # Update metadata
#         artifact.metadata.last_modified_by = modified_by
#         artifact.metadata.last_modified_at = datetime.now()
#         artifact.version += 1
        
#         # Return new artifact with updated content
#         return Artifact(
#             id=artifact.id,
#             type=artifact.type,
#             content=new_content,
#             metadata=artifact.metadata
#         )
    
#     @staticmethod
#     def get_artifacts_by_type(state: AgentState, artifact_type: str) -> List[Artifact]:
#         """Get all artifacts of a specific type"""
#         artifacts = state.get("artifacts", {})
#         return [artifact for artifact in artifacts.values() if artifact.type == artifact_type]
    
#     @staticmethod
#     def get_artifacts_by_owner(state: AgentState, owner: str) -> List[Artifact]:
#         """Get all artifacts created by a specific agent"""
#         artifacts = state.get("artifacts", {})
#         return [artifact for artifact in artifacts.values() if artifact.metadata.created_by == owner]
    
#     @staticmethod
#     def get_latest_artifact(state: AgentState, artifact_type: str) -> Optional[Artifact]:
#         """Get the most recent artifact of a specific type"""
#         artifacts = ArtifactManager.get_artifacts_by_type(state, artifact_type)
#         if not artifacts:
#             return None
#         return max(artifacts, key=lambda x: x.version)

# # Agent functions with simplified artifact management
# def analyst_agent(state: AgentState) -> dict:
#     """Analyst creates requirement classifications, SRL, and RM"""
#     user_input = state["user_input"]
#     artifacts = state.get("artifacts", {})
    
#     # Create or update requirement classification
#     req_classifications = RequirementsClassificationList(
#         req_class_id=[
#             RequirementClassification(
#                 requirement_id="REQ001",
#                 requirement_text=f"System shall handle: {user_input}",
#                 category=RequirementCategory.FUNCTIONAL,
#                 priority=RequirementPriority.HIGH
#             )
#         ]
#     )
    
#     classification_artifact = ArtifactManager.create_artifact(
#         "req_classification_001",
#         "requirement_classification", 
#         req_classifications,
#         "analyst"
#     )
    
#     # Create system requirements list
#     srl = SystemRequirementsList(
#         requirements=[
#             SystemRequirement(
#                 id="SYS001",
#                 description=f"System requirement for: {user_input}",
#                 source_classification_id="REQ001",
#                 acceptance_criteria=["Criterion 1", "Criterion 2"]
#             )
#         ],
#         version="1.0",
#         last_updated=datetime.now()
#     )
    
#     srl_artifact = ArtifactManager.create_artifact(
#         "srl_001",
#         "system_requirements_list",
#         srl,
#         "analyst"
#     )
    
#     # Create requirement model
#     rm = RequirementModel(
#         use_cases=[
#             UseCase(
#                 id="UC001",
#                 name="Primary Use Case",
#                 actors=[UseCaseActor(name="User", type="primary", description="End user")],
#                 preconditions=["System is running"],
#                 postconditions=["Task completed"],
#                 main_flow=["Step 1", "Step 2", "Step 3"]
#             )
#         ],
#         system_boundary="Web Application System",
#         plantuml_diagram="@startuml\nactor User\nUser -> System : Request\n@enduml"
#     )
    
#     rm_artifact = ArtifactManager.create_artifact(
#         "rm_001", 
#         "requirement_model",
#         rm,
#         "analyst"
#     )
    
#     # Update state with new artifacts
#     new_artifacts = artifacts.copy()
#     new_artifacts.update({
#         "req_classification_001": classification_artifact,
#         "srl_001": srl_artifact,
#         "rm_001": rm_artifact
#     })
    
#     return {
#         "artifacts": new_artifacts,
#         "response": "[Analyst] Created requirement classification, SRL, and RM artifacts"
#     }

# def archivist_agent(state: AgentState) -> dict:
#     """Archivist creates/updates SRS and technical specs, can read all artifacts"""
#     user_input = state["user_input"]
#     artifacts = state.get("artifacts", {})
    
#     # Read SRL from analyst if available
#     srl_artifact = artifacts.get("srl_001")
#     srl_info = ""
#     if srl_artifact:
#         srl_info = f"Using SRL version {srl_artifact.version} from analyst"
    
#     # Read validation report from reviewer if available
#     validation_artifact = artifacts.get("validation_report_001")
#     validation_feedback = ""
#     if validation_artifact and isinstance(validation_artifact.content, BaseModel):
#         validation_feedback = f"Incorporating feedback from validation report v{validation_artifact.version}"
    
#     # Create or update SRS
#     existing_srs = artifacts.get("srs_001")
    
#     if existing_srs:
#         # Update existing SRS
#         new_version = f"{float(existing_srs.content.version) + 0.1:.1f}"
#         srs = SRSDocument(
#             version=new_version,
#             introduction=f"Updated SRS for: {user_input}",
#             system_overview="Updated system overview content",
#             requirements=[],  # Would be populated from SRL
#             validation_status="updated" if validation_feedback else "draft",
#             review_feedback=validation_feedback if validation_feedback else None
#         )
#         srs_artifact = ArtifactManager.update_artifact(existing_srs, srs, "archivist")
#     else:
#         # Create new SRS
#         srs = SRSDocument(
#             version="1.0",
#             introduction=f"SRS for: {user_input}",
#             system_overview="System overview content",
#             requirements=[],  # Would be populated from SRL
#             validation_status="draft",
#             review_feedback=None
#         )
#         srs_artifact = ArtifactManager.create_artifact(
#             "srs_001",
#             "srs_document", 
#             srs,
#             "archivist",
#             dependencies=["srl_001"] if srl_artifact else []
#         )
    
#     # Create/update technical specifications
#     tech_specs = {
#         "database_schema": f"Schema for {user_input}",
#         "api_specifications": f"API specs for {user_input}", 
#         "deployment_config": "Updated deployment configuration",
#         "based_on_srl": srl_info,
#         "validation_feedback": validation_feedback
#     }
    
#     existing_tech_specs = artifacts.get("tech_specs_001")
#     if existing_tech_specs:
#         tech_specs_artifact = ArtifactManager.update_artifact(existing_tech_specs, tech_specs, "archivist")
#     else:
#         tech_specs_artifact = ArtifactManager.create_artifact(
#             "tech_specs_001",
#             "technical_specifications",
#             tech_specs,
#             "archivist"
#         )
    
#     # Update state
#     new_artifacts = artifacts.copy()
#     new_artifacts.update({
#         "srs_001": srs_artifact,
#         "tech_specs_001": tech_specs_artifact
#     })
    
#     return {
#         "artifacts": new_artifacts,
#         "response": f"[Archivist] Updated SRS and technical specs. {srl_info} {validation_feedback}"
#     }

# def reviewer_agent(state: AgentState) -> dict:
#     """Reviewer creates validation reports and review documents, can read all artifacts"""
#     artifacts = state.get("artifacts", {})
    
#     # Read SRS from archivist
#     srs_artifact = artifacts.get("srs_001")
#     srs_feedback = ""
#     validation_artifact = None
    
#     if srs_artifact and isinstance(srs_artifact.content, BaseModel):
#         srs_feedback = f"Reviewed SRS version {srs_artifact.content.version}"
        
#         # Create validation report
#         validation_report = ValidationReport(
#             report_id="VR001",
#             srs_version=srs_artifact.content.version,
#             validation_date=datetime.now(),
#             overall_quality_score=0.85,
#             consistency_check_passed=True,
#             issues=[
#                 ValidationIssue(
#                     issue_id="ISS001",
#                     severity="minor",
#                     description="Minor formatting issue in section 2",
#                     affected_requirement_ids=["SYS001"],
#                     recommendation="Update formatting for consistency"
#                 )
#             ],
#             recommendations=["Add more detailed acceptance criteria", "Include performance requirements"]
#         )
        
#         existing_validation = artifacts.get("validation_report_001")
#         if existing_validation:
#             validation_artifact = ArtifactManager.update_artifact(existing_validation, validation_report, "reviewer")
#         else:
#             validation_artifact = ArtifactManager.create_artifact(
#                 "validation_report_001",
#                 "validation_report",
#                 validation_report,
#                 "reviewer",
#                 dependencies=["srs_001"]
#             )
    
#     # Read requirement model from analyst
#     rm_artifact = artifacts.get("rm_001")
#     rm_info = ""
#     if rm_artifact:
#         rm_info = f"Also reviewed RM version {rm_artifact.version}"
    
#     # Create review document
#     all_artifact_ids = list(artifacts.keys())
#     review_doc = ReviewDocument(
#         review_id="RD001",
#         reviewed_artifacts=all_artifact_ids,
#         reviewer_comments=f"Overall quality is good. {srs_feedback} {rm_info}",
#         approval_status="needs_revision" if validation_artifact else "approved"
#     )
    
#     existing_review = artifacts.get("review_doc_001")
#     if existing_review:
#         review_artifact = ArtifactManager.update_artifact(existing_review, review_doc, "reviewer")
#     else:
#         review_artifact = ArtifactManager.create_artifact(
#             "review_doc_001",
#             "review_document",
#             review_doc,
#             "reviewer"
#         )
    
#     # Create/update quality metrics
#     quality_metrics = {
#         "completeness_score": 0.90,
#         "consistency_score": 0.85,
#         "testability_score": 0.80,
#         "review_time_minutes": 45,
#         "artifacts_reviewed": len(all_artifact_ids),
#         "srs_reviewed": srs_feedback != "",
#         "rm_reviewed": rm_info != ""
#     }
    
#     existing_metrics = artifacts.get("quality_metrics_001")
#     if existing_metrics:
#         metrics_artifact = ArtifactManager.update_artifact(existing_metrics, quality_metrics, "reviewer")
#     else:
#         metrics_artifact = ArtifactManager.create_artifact(
#             "quality_metrics_001",
#             "quality_metrics",
#             quality_metrics,
#             "reviewer"
#         )
    
#     # Update state
#     new_artifacts = artifacts.copy()
#     new_artifacts.update({
#         "review_doc_001": review_artifact,
#         "quality_metrics_001": metrics_artifact
#     })
    
#     if validation_artifact:
#         new_artifacts["validation_report_001"] = validation_artifact
    
#     return {
#         "artifacts": new_artifacts,
#         "response": f"[Reviewer] Created/updated validation report and review documents. {srs_feedback} {rm_info}"
#     }

# # Helper functions for easy artifact access
# def get_srs_document(state: AgentState) -> Optional[SRSDocument]:
#     """Get the current SRS document content"""
#     srs_artifact = state.get("artifacts", {}).get("srs_001")
#     if srs_artifact and isinstance(srs_artifact.content, BaseModel):
#         return srs_artifact.content
#     return None

# def get_system_requirements_list(state: AgentState) -> Optional[SystemRequirementsList]:
#     """Get the current SRL content"""
#     srl_artifact = state.get("artifacts", {}).get("srl_001")
#     if srl_artifact and isinstance(srl_artifact.content, BaseModel):
#         return srl_artifact.content
#     return None

# def get_validation_report(state: AgentState) -> Optional[ValidationReport]:
#     """Get the current validation report content"""
#     validation_artifact = state.get("artifacts", {}).get("validation_report_001")
#     if validation_artifact and isinstance(validation_artifact.content, BaseModel):
#         return validation_artifact.content
#     return None

# def print_artifact_summary(state: AgentState):
#     """Print summary of all artifacts"""
#     artifacts = state.get("artifacts", {})
#     print(f"\n=== Artifact Summary ({len(artifacts)} artifacts) ===")
    
#     for artifact_id, artifact in artifacts.items():
#         print(f"\nID: {artifact_id}")
#         print(f"Type: {artifact.type}")
#         print(f"Owner: {artifact.metadata.created_by}")
#         print(f"Version: {artifact.version}")
#         print(f"Last Modified: {artifact.metadata.last_modified_at}")
#         if artifact.metadata.dependencies:
#             print(f"Depends on: {', '.join(artifact.metadata.dependencies)}")
        
#         # Print content summary
#         if isinstance(artifact.content, BaseModel):
#             print(f"Content: {type(artifact.content).__name__} Pydantic model")
#         elif isinstance(artifact.content, dict):
#             print(f"Content: Dictionary with {len(artifact.content)} keys")
#         else:
#             print(f"Content: {type(artifact.content).__name__}")

# # Example usage demonstrating cross-agent artifact access
# if __name__ == "__main__":
#     # Initialize state
#     initial_state: AgentState = {
#         "user_input": "Create a user authentication system",
#         "response": "",
#         "phase": "initial",
#         "iteration_count": 0,
#         "artifacts": {},
#         "execution_history": []
#     }
    
#     print("=== Testing Cross-Agent Artifact Access ===")
    
#     # 1. Analyst creates artifacts
#     print("\n1. Analyst creates initial artifacts:")
#     result = analyst_agent(initial_state)
#     print_artifact_summary(result)
    
#     # 2. Archivist reads analyst artifacts and creates SRS
#     print("\n2. Archivist reads analyst artifacts and creates SRS:")
#     result = archivist_agent(result)
#     print_artifact_summary(result)
    
#     # 3. Reviewer reads all artifacts and creates validation report
#     print("\n3. Reviewer reads all artifacts and creates validation:")
#     result = reviewer_agent(result)
#     print_artifact_summary(result)
    
#     # 4. Archivist reads reviewer's validation report and updates SRS
#     print("\n4. Archivist reads validation report and updates SRS:")
#     result["user_input"] = "Update SRS based on review feedback"
#     result = archivist_agent(result)
#     print_artifact_summary(result)
    
#     print("\n=== Final SRS Content ===")
#     srs = get_srs_document(result)
#     if srs:
#         print(f"SRS Version: {srs.version}")
#         print(f"Introduction: {srs.introduction}")
#         print(f"Validation Status: {srs.validation_status}")
#         print(f"Review Feedback: {srs.review_feedback}")
    
#     print("\n=== Final Validation Report ===")
#     validation = get_validation_report(result)
#     if validation:
#         print(f"Report ID: {validation.report_id}")
#         print(f"Quality Score: {validation.overall_quality_score}")
#         print(f"Issues Found: {len(validation.issues)}")
#         print(f"Recommendations: {len(validation.recommendations)}")