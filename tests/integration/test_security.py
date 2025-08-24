from uuid import uuid4

from src.shared.security import get_password_hasher, get_token_provider, Role


def test_password_hash_roundtrip():
    hasher = get_password_hasher()
    h = hasher.hash("P@ssw0rd!!")
    assert hasher.verify("P@ssw0rd!!", h)
    assert not hasher.verify("wrong", h)


def test_jwt_cycle():
    provider = get_token_provider()
    sub = uuid4()
    ten = uuid4()
    token = provider.encode(sub=sub, tenant_id=ten, role=Role.TENANT_ADMIN)
    claims = provider.decode(token)
    assert claims["sub"] == str(sub)
    assert claims["tenant_id"] == str(ten)
    assert claims["role"] == Role.TENANT_ADMIN.value
