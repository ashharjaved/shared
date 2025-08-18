from typing import Any

class TenantContextService:
    @staticmethod
    def get_tenant_id(principal: Any) -> str:
        # Accept both object-like and dict-like principals
        if hasattr(principal, "tenant_id"):
            return getattr(principal, "tenant_id")
        if isinstance(principal, dict) and "tenant_id" in principal:
            return principal["tenant_id"]
        raise ValueError("Invalid principal: tenant_id missing")
