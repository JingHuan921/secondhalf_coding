from typing import Literal, List, Optional
from enum import Enum
from pydantic import BaseModel, Field 

from .shared import *

class RequirementModel(BaseModel):
    diagram_base64: Optional[str] = None
    diagram_path: Optional[str] = None
    uml_fmt_content: Optional[str] = None
    summary: Optional[str] = Field(default=None, description="Brief one-sentence summary of the requirement model")

