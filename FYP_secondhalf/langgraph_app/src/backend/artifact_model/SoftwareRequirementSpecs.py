from typing import Literal, List
from enum import Enum
from pydantic import BaseModel, Field 

from .shared import *



class SoftwareRequirementSpecs(BaseModel): 
    """Response to the user for a Software Requirement Specs (SRS)"""
    brief_introduction: str
    product_description: str
    functional_requirements: str
    non_functional_requirements: str
    reference_documents_id: List[str]
    references: str
