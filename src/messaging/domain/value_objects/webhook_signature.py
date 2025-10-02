"""
Webhook Signature Value Object
Validates WhatsApp webhook signatures (HMAC SHA256).
"""
import hmac
import hashlib

from shared.domain.base_value_object import BaseValueObject


class WebhookSignature(BaseValueObject):
    """
    Value object for validating WhatsApp webhook signatures.
    
    WhatsApp signs payloads using HMAC SHA256 with app secret.
    Signature format: sha256=<hex_digest>
    """
    
    def __init__(self, signature: str, payload: bytes, app_secret: str):
        self.signature = signature
        self.payload = payload
        self.app_secret = app_secret
        
        if not self.is_valid():
            raise ValueError("Invalid webhook signature")
    
    def is_valid(self) -> bool:
        """Verify signature against payload."""
        expected = hmac.new(
            self.app_secret.encode('utf-8'),
            self.payload,
            hashlib.sha256
        ).hexdigest()
        
        # Remove 'sha256=' prefix if present
        sig = self.signature.replace('sha256=', '')
        
        # Constant-time comparison
        return hmac.compare_digest(sig, expected)
    
    def __str__(self) -> str:
        return f"WebhookSignature(valid={self.is_valid()})"