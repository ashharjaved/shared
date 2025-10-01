"""Encryption service adapter using AWS KMS or local encryption."""

import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import boto3
from typing import Optional
import logging

from src.messaging.domain.interfaces.external_services import EncryptionService

logger = logging.getLogger(__name__)


class EncryptionAdapter(EncryptionService):
    """
    Encryption implementation using AWS KMS in production
    and local AES encryption in development.
    """
    
    def __init__(self, use_kms: bool = False, kms_key_id: Optional[str] = None):
        self.use_kms = use_kms and kms_key_id
        self.kms_key_id = kms_key_id
        
        if self.use_kms:
            self.kms_client = boto3.client('kms')
        else:
            # Use local encryption key from environment
            key = os.getenv('ENCRYPTION_KEY', '')
            if not key:
                # Generate a default key for development (NOT FOR PRODUCTION!)
                logger.warning("Using default encryption key - NOT FOR PRODUCTION")
                key = 'dev-key-32-chars-for-aes-256bit'
            
            # Ensure key is 32 bytes for AES-256
            self.local_key = key.encode('utf-8')[:32].ljust(32, b'\0')
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt sensitive data."""
        if not plaintext:
            return plaintext
        
        try:
            if self.use_kms:
                return self._encrypt_with_kms(plaintext)
            else:
                return self._encrypt_local(plaintext)
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise ValueError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt sensitive data."""
        if not ciphertext:
            return ciphertext
        
        try:
            if self.use_kms:
                return self._decrypt_with_kms(ciphertext)
            else:
                return self._decrypt_local(ciphertext)
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise ValueError(f"Failed to decrypt data: {e}")
    
    def _encrypt_local(self, plaintext: str) -> str:
        """Local AES-256 encryption."""
        # Generate random IV
        iv = os.urandom(16)
        
        # Pad the plaintext
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        
        # Encrypt
        cipher = Cipher(
            algorithms.AES(self.local_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV and encrypted data
        combined = iv + encrypted
        
        # Base64 encode for storage
        return base64.b64encode(combined).decode('utf-8')
    
    def _decrypt_local(self, ciphertext: str) -> str:
        """Local AES-256 decryption."""
        # Base64 decode
        combined = base64.b64decode(ciphertext)
        
        # Extract IV and encrypted data
        iv = combined[:16]
        encrypted = combined[16:]
        
        # Decrypt
        cipher = Cipher(
            algorithms.AES(self.local_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(encrypted) + decryptor.finalize()
        
        # Unpad
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        return plaintext.decode('utf-8')
    
    def _encrypt_with_kms(self, plaintext: str) -> str:
        """AWS KMS encryption."""
        response = self.kms_client.encrypt(
            KeyId=self.kms_key_id,
            Plaintext=plaintext.encode('utf-8')
        )
        # Return base64 encoded ciphertext
        return base64.b64encode(response['CiphertextBlob']).decode('utf-8')
    
    def _decrypt_with_kms(self, ciphertext: str) -> str:
        """AWS KMS decryption."""
        ciphertext_blob = base64.b64decode(ciphertext)
        response = self.kms_client.decrypt(CiphertextBlob=ciphertext_blob)
        return response['Plaintext'].decode('utf-8')