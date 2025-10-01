"""Outbox worker for processing queued events."""

import asyncio
import logging
import signal
import sys
from typing import Optional
from datetime import datetime
import json

from src.messaging.infrastructure.outbox.outbox_service import OutboxService
from src.messaging.application.services.message_service import MessageService
from src.messaging.infrastructure.middleware.tenant_context import TenantContextManager
#from src.shared.infrastructure.database import get_session, get_engine
from src.shared.database import get_async_session
from src.messaging.infrastructure.dependencies import (
    get_message_service,
    get_redis
)

logger = logging.getLogger(__name__)


class OutboxWorker:
    """Worker for processing outbox events."""
    
    def __init__(
        self,
        outbox_service: OutboxService,
        message_service: MessageService,
        tenant_context: TenantContextManager,
        poll_interval: int = 5
    ):
        self.outbox_service = outbox_service
        self.message_service = message_service
        self.tenant_context = tenant_context
        self.poll_interval = poll_interval
        self.running = False
        self.tasks = set()
    
    async def start(self):
        """Start the worker."""
        logger.info("Starting outbox worker...")
        self.running = True
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
        while self.running:
            try:
                # Get pending events
                events = await self.outbox_service.get_pending_events(limit=10)
                
                if events:
                    logger.info(f"Processing {len(events)} outbox events")
                    
                    # Process events concurrently
                    tasks = []
                    for event in events:
                        task = asyncio.create_task(self._process_event(event))
                        tasks.append(task)
                        self.tasks.add(task)
                        task.add_done_callback(self.tasks.discard)
                    
                    # Wait for all tasks to complete
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Sleep before next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _process_event(self, event: dict):
        """Process a single outbox event."""
        try:
            event_type = event["event_type"]
            tenant_id = event["tenant_id"]
            
            # Set tenant context
            await self.tenant_context.set_tenant_context(tenant_id)
            
            # Process based on event type
            if event_type == "message.send_requested":
                await self._process_send_message(event)
            elif event_type == "message.retry":
                await self._process_retry_message(event)
            else:
                logger.warning(f"Unknown event type: {event_type}")
            
            # Mark as processed
            await self.outbox_service.mark_processed(event["id"])
            
        except Exception as e:
            logger.error(f"Failed to process event {event['id']}: {e}")
            await self.outbox_service.mark_failed(event["id"], str(e))
        finally:
            # Clear tenant context
            await self.tenant_context.clear_tenant_context()
    
    async def _process_send_message(self, event: dict):
        """Process send message event."""
        payload = event["payload"]
        message_id = payload["message_id"]
        tenant_id = event["tenant_id"]
        
        logger.info(f"Processing outbound message {message_id}")
        
        await self.message_service.process_outbound_message(
            message_id=message_id,
            tenant_id=tenant_id
        )
    
    async def _process_retry_message(self, event: dict):
        """Process retry message event."""
        payload = event["payload"]
        message_id = payload["message_id"]
        tenant_id = event["tenant_id"]
        retry_count = payload.get("retry_count", 0)
        
        logger.info(f"Retrying message {message_id} (attempt #{retry_count})")
        
        await self.message_service.process_outbound_message(
            message_id=message_id,
            tenant_id=tenant_id
        )
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping outbox worker...")
        self.running = False
        
        # Wait for remaining tasks
        if self.tasks:
            logger.info(f"Waiting for {len(self.tasks)} tasks to complete...")
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Outbox worker stopped")


async def main():
    """Main entry point for outbox worker."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize dependencies
    engine = get_engine()
    async with engine.begin() as conn:
        session = get_session()
        redis = await get_redis()
        
        # Create services
        outbox_service = OutboxService(session)
        message_service = await get_message_service(session, redis)
        tenant_context = TenantContextManager(session)
        
        # Create and start worker
        worker = OutboxWorker(
            outbox_service=outbox_service,
            message_service=message_service,
            tenant_context=tenant_context,
            poll_interval=5
        )
        
        try:
            await worker.start()
        finally:
            await worker.stop()
            await redis.close()
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())