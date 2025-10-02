# =============================================================================
# FILE: src/modules/whatsapp/infrastructure/persistence/repositories/README.md
# =============================================================================
"""
# WhatsApp Repository Layer

## Overview

This folder contains SQLAlchemy implementations of domain repository interfaces.
All repositories follow the shared `SQLAlchemyRepository` base class pattern.

## Key Features

### 1. Entity ↔ Model Mapping
- `_to_entity()`: Convert ORM model → Domain entity
- `_to_model()`: Convert Domain entity → ORM model
- Handles value object conversions (PhoneNumber, AccessToken, etc.)

### 2. Encryption
- Access tokens automatically encrypted/decrypted via `EncryptedString` type
- Uses shared `EncryptionManager` with AES-256-GCM
- No explicit encrypt/decrypt calls needed in repository

### 3. RLS (Row-Level Security)
- Session must have RLS context set before calling repositories
- Example:
  ```python
  async with RLSManager(session) as rls:
      await rls.set_context(tenant_id=tenant_id, user_id=user_id)
      channel = await channel_repo.get_by_id(channel_id)
  ```
- RLS enforced at PostgreSQL level via `app.jwt_tenant` GUC

### 4. Idempotency
- `get_outbound_by_idempotency_key()` prevents duplicate message sends
- Idempotency key format: `SHA256(account_id:to_phone:content:timestamp)`

### 5. Query Optimization
- Indexes on foreign keys, status, timestamps
- Composite indexes for common query patterns
- Use `.options(selectinload())` for eager loading if needed

## Repository Classes

### SQLAlchemyChannelRepository
- **Purpose**: Manage WhatsApp Business Account channels
- **Key Methods**:
  - `get_by_phone_number_id()`: Lookup by WhatsApp phone number ID
  - `get_by_organization()`: Get all channels for tenant
  - `get_active_channels()`: Get verified, active channels only

### SQLAlchemyMessageRepository
- **Purpose**: Manage inbound/outbound messages
- **Key Methods**:
  - `save_inbound()`, `save_outbound()`: Persist messages
  - `get_outbound_by_idempotency_key()`: Prevent duplicates
  - `get_failed_for_retry()`: Retrieve failed messages for retry worker
  - `update_outbound()`: Update message status (sent → delivered → read)

### RedisRateLimiter
- **Purpose**: Enforce WhatsApp API rate limits (80/250 msg/sec)
- **Key Methods**:
  - `check_rate_limit()`: Check if within limit (non-destructive)
  - `consume_token()`: Consume tokens (destructive)
  - `get_remaining_tokens()`: Get current usage
- **Algorithm**: Token bucket with Redis INCR + TTL

## Usage Example

```python
from shared.infrastructure.database import SQLAlchemyUnitOfWork, RLSManager
from whatsapp.infrastructure.persistence.repositories import (
    SQLAlchemyChannelRepository,
    SQLAlchemyMessageRepository
)

async def send_message(tenant_id: UUID, channel_id: UUID, ...):
    async with SQLAlchemyUnitOfWork() as uow:
        # Set RLS context
        async with RLSManager(uow.session) as rls:
            await rls.set_context(tenant_id=tenant_id, user_id=user_id)
            
            # Initialize repositories
            channel_repo = SQLAlchemyChannelRepository(uow.session)
            message_repo = SQLAlchemyMessageRepository(uow.session)
            
            # Get channel
            channel = await channel_repo.get_by_id(channel_id)
            if not channel:
                raise NotFoundException("Channel not found")
            
            # Check idempotency
            existing = await message_repo.get_outbound_by_idempotency_key(key)
            if existing:
                return existing  # Already sent
            
            # Create message
            message = OutboundMessage(...)
            saved = await message_repo.save_outbound(message)
            
            # Commit transaction
            await uow.commit()
            
            return saved
```