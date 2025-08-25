from typing import Literal, List
from enum import Enum
from pydantic import BaseModel, Field 

from .shared import *

class RMRequirement(BaseModel):
    requirement_id: str
    requirement_text: str
    category: RequirementCategory
    priority: RequirementPriority

class RMEntity(BaseModel):
    entity_id: str
    name: str
    type: str

class RMRelationship(BaseModel):
    source_id: str
    target_id: str
    type: str

class RequirementsModel(BaseModel):
    entities: List[RMEntity]
    requirements: List[RMRequirement]
    relationships: List[RMRelationship]
