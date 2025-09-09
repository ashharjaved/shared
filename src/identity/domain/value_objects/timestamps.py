# src/identity/domain/value_objects/timestamps.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class Timestamps:
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def _utcnow() -> datetime:
        # always store tz-aware UTC
        return datetime.now(timezone.utc)

    @classmethod
    def now(cls) -> "Timestamps":
        now = cls._utcnow()
        return cls(created_at=now, updated_at=now)

    @classmethod
    def from_datetimes(cls, created_at: datetime, updated_at: datetime) -> "Timestamps":
        # trust ORM to supply tz-aware datetimes; if naive, treat as UTC
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return cls(created_at=created_at, updated_at=updated_at)

    def update_timestamp(self) -> "Timestamps":
        return Timestamps(self.created_at, self._utcnow())
