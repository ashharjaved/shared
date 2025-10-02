"""
Use Case Base Class
Abstract orchestrator for business workflows
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class UseCase(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for use cases.
    
    Use cases orchestrate business workflows that may span multiple
    commands/queries and coordinate between multiple services.
    
    Type Parameters:
        TInput: Input data type
        TOutput: Output/result type
        
    Example:
        class RegisterUserUseCase(UseCase[RegisterUserInput, UserDTO]):
            async def execute(self, input_data: RegisterUserInput) -> UserDTO:
                # Validate, create user, send welcome email, return DTO
                pass
    """
    
    @abstractmethod
    async def execute(self, input_data: TInput) -> TOutput:
        """
        Execute the use case.
        
        Args:
            input_data: Input parameters for the use case
            
        Returns:
            Result of use case execution
            
        Raises:
            BusinessRuleViolationError: If business rules violated
            ValidationError: If input invalid
        """
        pass
    
    async def __call__(self, input_data: TInput) -> TOutput:
        """
        Make use case callable directly.
        
        Adds logging around execution.
        
        Args:
            input_data: Input parameters
            
        Returns:
            Use case result
        """
        use_case_name = self.__class__.__name__
        
        logger.info(
            f"Executing use case: {use_case_name}",
            extra={"use_case": use_case_name},
        )
        
        try:
            result = await self.execute(input_data)
            
            logger.info(
                f"Use case completed successfully: {use_case_name}",
                extra={"use_case": use_case_name},
            )
            
            return result
        except Exception as e:
            logger.error(
                f"Use case execution failed: {use_case_name}",
                extra={"use_case": use_case_name, "error": str(e)},
            )
            raise