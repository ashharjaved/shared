"""
Base Command Handler
Abstract base for all command handlers
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from shared.application.base_command import BaseCommand
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

TCommand = TypeVar("TCommand", bound=BaseCommand)
TResult = TypeVar("TResult")


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """
    Abstract base class for command handlers.
    
    Command handlers execute write operations and enforce business rules.
    They orchestrate domain logic and coordinate with repositories.
    
    Type Parameters:
        TCommand: Command type this handler processes
        TResult: Return type of the handler
        
    Example:
        class CreateUserCommandHandler(CommandHandler[CreateUserCommand, User]):
            async def handle(self, command: CreateUserCommand) -> User:
                # Validate, create entity, persist, return
                pass
    """
    
    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """
        Handle the command and return result.
        
        Args:
            command: Command to execute
            
        Returns:
            Result of command execution
            
        Raises:
            BusinessRuleViolationError: If business rules violated
            ValidationError: If command data invalid
        """
        pass
    
    async def __call__(self, command: TCommand) -> TResult:
        """
        Make handler callable directly.
        
        Adds logging around command execution.
        
        Args:
            command: Command to execute
            
        Returns:
            Result of command execution
        """
        command_name = command.__class__.__name__
        
        logger.info(
            f"Executing command: {command_name}",
            extra={"command": command_name},
        )
        
        try:
            result = await self.handle(command)
            
            logger.info(
                f"Command executed successfully: {command_name}",
                extra={"command": command_name},
            )
            
            return result
        except Exception as e:
            logger.error(
                f"Command execution failed: {command_name}",
                extra={"command": command_name, "error": str(e)},
            )
            raise