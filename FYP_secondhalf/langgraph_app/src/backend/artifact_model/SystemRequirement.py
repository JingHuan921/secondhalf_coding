from typing import Literal, List
from enum import Enum
from pydantic import BaseModel, Field 

from .shared import *

class SystemRequirement(BaseModel):
    requirement_id: str
    requirement_statement: str
    category: RequirementCategory
    priority: RequirementPriority

class SystemRequirementsList(BaseModel):
    srl: List[SystemRequirement]
