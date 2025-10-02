from typing import Literal, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

from .shared import *

class RequirementClassification(BaseModel):
    """Response to the user for each requirement"""
    requirement_id: str
    requirement_text: str
    category: RequirementCategory
    priority: RequirementPriority

class RequirementsClassificationList(BaseModel):
    """Respond to the user with classification for all requirement items"""
    req_class_id: List[RequirementClassification]
    summary: Optional[str] = Field(default=None, description="Brief one-sentence summary of what was classified")
