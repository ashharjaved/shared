# src/messaging/domain/services/idempotency_rules.py
"""Idempotency enforcement rules for messaging operations."""

from dataclasses import dataclass
from typing import Optional, Set
from datetime import datetime, timedelta

from ..types import WhatsAppMessageId, DedupeKey, TenantId


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Idempotency key for deduplication."""
    key: str
    tenant_id: TenantId
    created_at: datetime
    expires_at: datetime


class IdempotencyRules:
    """
    Pure domain service for idempotency enforcement.
    
    Defines rules for preventing duplicate message processing
    and outbound send deduplication.
    
    Example:
        rules = IdempotencyRules()
        key = rules.generate_inbound_key(wa_message_id, tenant_id)
        is_duplicate = rules.is_duplicate_operation(key, seen_keys)
    """
    
    @staticmethod
    def generate_inbound_key(
        wa_message_id: WhatsAppMessageId, 
        tenant_id: TenantId
    ) -> DedupeKey:
        """
        Generate idempotency key for inbound webhook processing.
        
        Args:
            wa_message_id: WhatsApp message ID from webhook
            tenant_id: Tenant receiving the message
            
        Returns:
            Canonical dedupe key for inbound processing
        """
        return DedupeKey(f"inbound:{tenant_id}:{wa_message_id}")
    
    @staticmethod
    def generate_outbound_key(
        content_hash: str,
        tenant_id: TenantId,
        to_msisdn: str
    ) -> DedupeKey:
        """
        Generate idempotency key for outbound message sending.
        
        Args:
            content_hash: Hash of message content
            tenant_id: Sending tenant
            to_msisdn: Recipient phone number
            
        Returns:
            Canonical dedupe key for outbound sending
        """
        return DedupeKey(f"outbound:{tenant_id}:{to_msisdn}:{content_hash}")
    
    @staticmethod
    def is_duplicate_operation(key: DedupeKey, seen_keys: Set[DedupeKey]) -> bool:
        """
        Check if operation key indicates duplicate.
        
        Args:
            key: Dedupe key to check
            seen_keys: Set of previously seen keys
            
        Returns:
            True if key represents duplicate operation
        """
        return key in seen_keys
    
    @staticmethod
    def should_dedupe_inbound(wa_message_id: Optional[WhatsAppMessageId]) -> bool:
        """
        Determine if inbound message should be deduplicated.
        
        Args:
            wa_message_id: WhatsApp message ID if present
            
        Returns:
            True if message should be checked for duplicates
        """
        return wa_message_id is not None
    
    @staticmethod
    def create_idempotency_key(
        key: str,
        tenant_id: TenantId,
        ttl_hours: int = 24
    ) -> IdempotencyKey:
        """
        Create idempotency key with expiration.
        
        Args:
            key: Raw key string
            tenant_id: Associated tenant
            ttl_hours: Time to live in hours
            
        Returns:
            IdempotencyKey with expiration
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=ttl_hours)
        
        return IdempotencyKey(
            key=key,
            tenant_id=tenant_id,
            created_at=now,
            expires_at=expires_at
        )
