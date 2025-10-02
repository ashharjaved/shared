"""
Create Organization Command
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from shared.application.base_command import BaseCommand
from shared.application.command_handler import CommandHandler
from shared.domain.result import Result, Success, Failure
from shared.infrastructure.observability.logger import get_logger

from src.identity.domain.entities.organization import Organization, Industry
from src.identity.domain.value_objects.organization_metadata import (
    OrganizationMetadata,
)
from src.identity.domain.exception import DuplicateSlugException
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


@dataclass(frozen=True)
class CreateOrganizationCommand(BaseCommand):
    """
    Command to create a new organization.
    
    Attributes:
        name: Organization name
        slug: URL-safe slug (unique)
        industry: Business vertical
        timezone: Timezone (default: UTC)
        language: Primary language (default: en)
        created_by: User ID who created this organization (for audit)
    """
    name: str
    slug: str
    industry: str
    timezone: str = "UTC"
    language: str = "en"
    created_by: UUID | None = None


class CreateOrganizationCommandHandler(CommandHandler[CreateOrganizationCommand, UUID]):
    """
    Handler for CreateOrganizationCommand.
    
    Creates a new organization with default configuration.
    """
    
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self.uow = uow
    
    async def handle(self, command: CreateOrganizationCommand) -> Result[UUID, str]:
        """
        Execute organization creation.
        
        Args:
            command: Create organization command
            
        Returns:
            Result with organization ID or error message
        """
        try:
            async with self.uow:
                # Check if slug already exists
                existing = await self.uow.organizations.get_by_slug(command.slug)
                if existing:
                    logger.warning(
                        f"Organization slug already exists: {command.slug}",
                        extra={"slug": command.slug},
                    )
                    return Failure(f"Organization slug '{command.slug}' already exists")
                
                # Parse industry
                try:
                    industry = Industry(command.industry.lower())
                except ValueError:
                    industry = Industry.OTHER
                
                # Create metadata
                metadata = OrganizationMetadata(
                    timezone=command.timezone,
                    language=command.language,
                )
                
                # Create organization entity
                organization = Organization.create(
                    id=uuid4(),
                    name=command.name,
                    slug=command.slug,
                    industry=industry,
                    metadata=metadata,
                )
                
                # Persist
                saved = await self.uow.organizations.add(organization)
                
                # Track for domain events
                self.uow.track_aggregate(organization)
                
                # Write audit log (NEW)
                audit_service = AuditLogService(self.uow.audit_logs)
                await audit_service.log(
                    action="organization_created",
                    organization_id=saved.id,
                    user_id=command.created_by,
                    resource_type="organization",
                    resource_id=saved.id,
                    metadata={
                        "name": command.name,
                        "slug": command.slug,
                        "industry": command.industry,
                    },
                )
                
                # Commit (publishes domain events to outbox)
                await self.uow.commit()
                
                logger.info(
                    f"Organization created: {saved.name}",
                    extra={
                        "organization_id": str(saved.id),
                        "slug": saved.slug,
                        "created_by": str(command.created_by) if command.created_by else None,
                    },
                )
                
                return Success(saved.id)
                
        except Exception as e:
            logger.error(
                f"Failed to create organization: {e}",
                extra={"command": command, "error": str(e)},
            )
            return Failure(f"Failed to create organization: {str(e)}")