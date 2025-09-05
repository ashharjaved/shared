# src/conversation/infrastructure/mappers.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast
from uuid import UUID

# Import domain entities / value objects
# Adjust import paths to your project layout if needed.
from src.conversation.domain.entities import (
    MenuFlow,
    ConversationSession,
    SessionStatus,
)
from src.conversation.domain.value_objects import (
    MenuDefinition,
    PhoneNumber,
)

# Import ORM models
from src.conversation.infrastructure.models import (
    MenuFlowORM,
    ConversationSessionORM,
)


# ------------------------------
# Utilities
# ------------------------------

def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return a timezone-aware (UTC) datetime or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _menu_def_to_json(defn: MenuDefinition | Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize MenuDefinition to a plain dict suitable for JSONB.
    Accepts either a MenuDefinition or a dict (already JSON).
    """
    if isinstance(defn, dict):
        return defn
    # Try preferred APIs in order; stay tolerant to implementation details
    # without coupling strictly to one.
    to_dict = getattr(defn, "to_dict", None)
    if callable(to_dict):
        return cast(Dict[str, Any], to_dict())  # pyright: ignore[reportUnknownArgumentType]
    if is_dataclass(defn):
        return asdict(defn)
    # Fallback: rely on __dict__ shallow copy (fields should be JSON-safe)
    return dict(defn.__dict__)  # type: ignore[dict-item]


def _menu_def_from_json(data: Dict[str, Any] | None) -> MenuDefinition:
    """
    Hydrate MenuDefinition from dict without assuming a specific constructor.
    Tries, in order: from_dict(d), MenuDefinition(**{'_raw': d}), MenuDefinition(d), MenuDefinition(**d)
    """
    d: Dict[str, Any] = data or {}
    # 1) from_dict
    from_dict = getattr(MenuDefinition, "from_dict", None)
    if callable(from_dict):
        try:
            return cast(MenuDefinition, from_dict(d))
        except Exception:
            pass
    # 2) **{'_raw': d}
    try:
        return MenuDefinition(_raw=d)  # type: ignore[call-arg]
    except Exception:
        pass
    # 3) single positional dict
    try:
        return MenuDefinition(d)  # type: ignore[call-arg]
    except Exception:
        pass
    # 4) **d
    return MenuDefinition(**d)  # type: ignore[arg-type]


def _phone_from_str(value: Optional[str]) -> Optional[PhoneNumber]:
    """Create PhoneNumber VO from raw string (or None)."""
    if value is None:
        return None
    return PhoneNumber(value)  # VO will validate E.164


def _phone_to_str(vo: Optional[PhoneNumber]) -> Optional[str]:
    """Extract E.164 string from PhoneNumber VO (or None)."""
    if vo is None:
        return None
    # Prefer .value/.as_e164 if implemented; else str(vo)
    if hasattr(vo, "value"):
        return vo.value  # type: ignore[attr-defined]
    if hasattr(vo, "as_e164") and callable(getattr(vo, "as_e164")):
        return vo.as_e164()  # type: ignore[no-any-return]
    return str(vo)


# ------------------------------
# MenuFlow mappers
# ------------------------------

def menu_flow_to_domain(row: MenuFlowORM) -> MenuFlow:
    """
    Convert ORM row -> domain entity (pure).
    """
    return MenuFlow(
        id=row.id,
        tenant_id=row.tenant_id,
        industry_type=row.industry_type,
        name=row.name,
        definition=_menu_def_from_json(getattr(row, "definition_jsonb", None)),
        version=row.version,
        is_active=row.is_active,
        is_default=row.is_default,
        created_by=row.created_by,
        created_at=_ensure_utc(row.created_at),
        updated_at=_ensure_utc(row.updated_at),
        deleted_at=_ensure_utc(row.deleted_at),
    )


def menu_flow_to_orm_new(entity: MenuFlow) -> MenuFlowORM:
    """
    Create a NEW ORM instance from a domain entity.
    Use this when INSERTing a new row.
    """
    return MenuFlowORM(
        id=entity.id,
        tenant_id=entity.tenant_id,
        industry_type=entity.industry_type,
        name=entity.name,
        definition_jsonb=_menu_def_to_json(entity.definition),
        version=entity.version,
        is_active=entity.is_active,
        is_default=entity.is_default,
        created_by=entity.created_by,
        # created_at/updated_at handled by DB defaults; you may set if needed:
        created_at=_ensure_utc(entity.created_at) if entity.created_at else None,
        updated_at=_ensure_utc(entity.updated_at) if entity.updated_at else None,
        deleted_at=_ensure_utc(entity.deleted_at) if entity.deleted_at else None,
    )


def menu_flow_update_orm(row: MenuFlowORM, entity: MenuFlow) -> None:
    """
    Mutate an EXISTING ORM row in-place to reflect the domain entity.
    Use this for UPDATEs (SQLAlchemy will track the changes).
    """
    row.industry_type = entity.industry_type
    row.name = entity.name
    row.definition_jsonb = _menu_def_to_json(entity.definition)
    row.version = entity.version
    row.is_active = entity.is_active
    row.is_default = entity.is_default
    row.deleted_at = _ensure_utc(entity.deleted_at)


# ------------------------------
# ConversationSession mappers
# ------------------------------

def session_to_domain(row: ConversationSessionORM) -> ConversationSession:
    """
    Convert ORM row -> domain entity (pure).
    """
    _phone = _phone_from_str(row.phone_number)
    if _phone is None:
        raise ValueError("ConversationSessionORM.phone_number is NULL; domain requires PhoneNumber")

    return ConversationSession(
        id=row.id,
        tenant_id=row.tenant_id,
        channel_id=row.channel_id,
        phone_number=_phone,
        current_menu_id=row.current_menu_id,
        context=getattr(row, "context_jsonb", {}) or {},
        status=row.status if isinstance(row.status, SessionStatus) else SessionStatus(row.status),
        message_count=row.message_count,
        created_at=_ensure_utc(row.created_at),
        last_activity=_ensure_utc(row.last_activity),
        expires_at=row.expires_at,
        updated_at=_ensure_utc(row.updated_at),
        deleted_at=_ensure_utc(row.deleted_at),
    )


def session_to_orm_new(entity: ConversationSession) -> ConversationSessionORM:
    """
    Create a NEW ORM instance from a domain entity.
    Use this when INSERTing a new row (rare; usually created via stored procedure).
    """
    values: dict[str, Any] = {
        "id": entity.id,
        "tenant_id": entity.tenant_id,
        "channel_id": entity.channel_id,
        "phone_number": _phone_to_str(entity.phone_number),
        "current_menu_id": entity.current_menu_id,
        "context": dict(entity.context or {}),
        "status": entity.status.value if hasattr(entity.status, "value") else str(entity.status),
        "message_count": entity.message_count,
    }
    if entity.created_at is not None:
        values["created_at"] = cast(datetime, _ensure_utc(entity.created_at))
    if entity.last_activity is not None:
        values["last_activity"] = cast(datetime, _ensure_utc(entity.last_activity))
    if entity.expires_at is not None:
        values["expires_at"] = cast(datetime, _ensure_utc(entity.expires_at))
    if entity.updated_at is not None:
        values["updated_at"] = cast(datetime, _ensure_utc(entity.updated_at))
    if entity.deleted_at is not None:
        values["deleted_at"] = cast(datetime, _ensure_utc(entity.deleted_at))
    return ConversationSessionORM(**values)


def session_update_orm(row: ConversationSessionORM, entity: ConversationSession) -> None:
    """
    Mutate an EXISTING ORM row in-place to reflect the domain entity.
    Typical updates: current_menu_id, context, status, message_count, last_activity, expires_at.
    """
    row.current_menu_id = entity.current_menu_id
    row.context_jsonb = dict(entity.context or {})
    row.status = entity.status if isinstance(entity.status, SessionStatus) else SessionStatus(str(entity.status))
    row.message_count = entity.message_count
    # Only assign when we have a concrete datetime; avoids None -> non-nullable column
    if entity.last_activity is not None:
        row.last_activity = cast(datetime, _ensure_utc(entity.last_activity))
    if entity.expires_at is not None:
        row.expires_at = cast(datetime, _ensure_utc(entity.expires_at))
    if entity.deleted_at is not None:
        row.deleted_at = cast(datetime, _ensure_utc(entity.deleted_at))

# ------------------------------
# Public facade (optional)
# ------------------------------

class ConversationMappers:
    """
    Optional façade if you prefer DI-friendly access to mappers.
    """

    @staticmethod
    def to_domain_menu(row: MenuFlowORM) -> MenuFlow:
        return menu_flow_to_domain(row)

    @staticmethod
    def to_domain_session(row: ConversationSessionORM) -> ConversationSession:
        return session_to_domain(row)

    @staticmethod
    def new_menu_row(entity: MenuFlow) -> MenuFlowORM:
        return menu_flow_to_orm_new(entity)

    @staticmethod
    def new_session_row(entity: ConversationSession) -> ConversationSessionORM:
        return session_to_orm_new(entity)

    @staticmethod
    def sync_menu_row(row: MenuFlowORM, entity: MenuFlow) -> None:
        menu_flow_update_orm(row, entity)

    @staticmethod
    def sync_session_row(row: ConversationSessionORM, entity: ConversationSession) -> None:
        session_update_orm(row, entity)
