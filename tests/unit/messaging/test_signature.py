import hmac, hashlib
from src.shared.security import verify_hub_signature

def test_valid_signature():
    secret = "s3cr3t"
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_hub_signature(body, secret, sig) is True

def test_invalid_signature():
    secret = "s3cr3t"
    body = b'{"hello":"world"}'
    sig = "sha256=deadbeef"
    assert verify_hub_signature(body, secret, sig) is False
