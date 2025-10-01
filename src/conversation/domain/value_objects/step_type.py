# src/conversation/domain/value_objects/step_type.py
"""Step type value object."""

from enum import Enum


class StepType(str, Enum):
    """Types of flow steps."""
    
    MESSAGE = "message"  # Bot sends message, no input expected
    QUESTION = "question"  # Bot asks question, expects freehand answer
    MENU = "menu"  # Bot shows numbered options
    FORM = "form"  # Collect structured data
    API_CALL = "api_call"  # Call external HTTP API
    CONDITION = "condition"  # Branch based on context
    END = "end"  # Terminal step
    
    def __str__(self) -> str:
        return self.value