# src/conversation/domain/services/step_executor.py
"""Step executor protocol."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from uuid import UUID

from src.conversation.domain.entities.flow_step import FlowStep
from src.conversation.domain.entities.session import Session


class StepExecutor(ABC):
    """Protocol for executing flow steps."""
    
    @abstractmethod
    async def execute(
        self,
        step: FlowStep,
        session: Session,
        user_input: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a flow step.
        
        Returns:
            {
                "response": "message to send to user",
                "next_step": "next step key or None",
                "context_updates": {"key": "value"},
                "actions_performed": [...]
            }
        """
        pass