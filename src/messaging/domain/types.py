# src/messaging/domain/types.py
"""Type aliases and domain-specific type definitions for messaging domain."""

from typing import NewType
from uuid import UUID
from datetime import datetime

# ID Types
ChannelId = NewType('ChannelId', UUID)
MessageId = NewType('MessageId', int)  # bigserial from DB
OutboxId = NewType('OutboxId', int)    # bigserial from DB
TenantId = NewType('TenantId', UUID)
WhatsAppMessageId = NewType('WhatsAppMessageId', str)
PhoneNumberId = NewType('PhoneNumberId', str)
MSISDN = NewType('MSISDN', str)  # E.164 format

# Domain primitives
VerifyToken = NewType('VerifyToken', str)
AppSecret = NewType('AppSecret', str)
DedupeKey = NewType('DedupeKey', str)
ErrorCode = NewType('ErrorCode', str)