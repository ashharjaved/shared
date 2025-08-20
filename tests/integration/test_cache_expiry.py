# tests/unit/platform/test_cache_expiry.py
from src.platform.infrastructure.cache import InMemoryTTLCache


import uuid

def test_cache_entry_expires():
    c = InMemoryTTLCache(ttl_seconds=0)
    tenant_id = uuid.uuid4()
    c.set(tenant_id, "k", "v")
    assert c.get(tenant_id, "k") is None
