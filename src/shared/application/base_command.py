"""
Base Command Contract for CQRS
All commands (write operations) inherit from this
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class BaseCommand:
    """
    Base class for all commands in the system.

    Commands represent write operations (create, update, delete).
    They are immutable data structures that carry all necessary information.

    Each command should have a corresponding CommandHandler.

    Example:
        @dataclass(frozen=True)
        class CreateUserCommand(BaseCommand):
            email: str
            password: str
            organization_id: UUID
    """

    # Optional: command metadata
    command_id: UUID | None = field(default=None, kw_only=True)
    issued_by: UUID | None = field(default=None, kw_only=True)  # User who issued the command
