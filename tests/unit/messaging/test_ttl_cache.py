from src.platform.infrastructure.cache import InMemoryTTLCache
import time

def test_ttl_cache_eviction():
    c = InMemoryTTLCache(ttl_seconds=1)
    c.set("t1","k","v")
    assert c.get("t1","k") == "v"
    time.sleep(1.2)
    assert c.get("t1","k") is None

def test_invalidate_and_clear():
    c = InMemoryTTLCache()
    c.set("t1","k","v")
    c.invalidate("t1","k")
    assert c.get("t1","k") is None
    c.set("t1","a","x"); c.set("t1","b","y")
    c.clear()
    assert c.get("t1","a") is None and c.get("t1","b") is None
