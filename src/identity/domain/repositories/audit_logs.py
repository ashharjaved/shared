from abc import ABC, abstractmethod

from identity.domain.entities.audit import AuditEntry


class AuditLogsRepository(ABC):
    """
    Repository interface for audits logs.
    
    All methods are async and raise domain exceptions on errors.
    Implementations must enforce RLS and tenant isolation.
    """
    @abstractmethod
    async def create_entry(self, entry: AuditEntry) -> AuditEntry:
        """
        Create an audit log entry.
        
        Args:
            entry: Audit log entry to create
            
        Returns:
            Created audit log entry
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def list_by_resource(self, entry_id: str) -> AuditEntry:
        """
        Retrieve tenant by ID.
        
        Args:
            tenant_id: Unique tenant identifier
            
        Returns:
            Tenant entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
