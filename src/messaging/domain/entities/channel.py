from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class Channel:
    """
    Pure domain entity representing a WhatsApp messaging channel bound to a tenant.

    NOTE:
    - Secrets (token, webhook_token) are present here as raw strings but must be
      encrypted/decrypted strictly in the Infrastructure layer. They are marked
      repr=False to avoid accidental logging.
    - All repository operations are *tenant-scoped* via DB RLS; the domain does
      not pass tenant_id to repos explicitly—Infra sets the GUC `app.jwt_tenant`.
    """

    id: UUID
    tenant_id: UUID

    phone_number_id: str  # Meta Graph "phone_number_id" (string identifier)
    business_phone: str   # E.164 string (validated via PhoneNumber VO in Message entity)

    # Sensitive credentials – never log these; infra must store encrypted-at-rest.
    token: str = field(repr=False)
    webhook_token: str = field(repr=False)
    webhook_url: str

    # Rate limits (None == unlimited/enforced elsewhere)
    rate_limit_per_second: Optional[int] = None
    monthly_message_limit: Optional[int] = None

    is_active: bool = True

    # Timestamps (set by DB or application services; domain keeps them as data)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
