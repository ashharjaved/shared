from uuid import UUID


def _to_uuid_or_none(value) -> UUID | None: # type: ignore
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None
    
__All__ = ["_to_uuid_or_none",]