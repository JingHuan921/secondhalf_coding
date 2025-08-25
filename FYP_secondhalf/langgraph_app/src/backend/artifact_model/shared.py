from typing import Literal, List
from enum import Enum
from pydantic import BaseModel, Field 

class RequirementCategory(str, Enum):
    FUNCTIONAL = "Functional"
    NON_FUNCTIONAL = "Non-functional"


class RequirementPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"