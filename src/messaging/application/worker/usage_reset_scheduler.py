"""Scheduler for resetting monthly usage."""

import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from src.messaging.application.services.channel_service import ChannelService
from src.shared_.database import get_async_session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class UsageResetScheduler:
    """Scheduler for resetting monthly channel usage."""
    
    def __init__(self, channel_service: ChannelService):
        self.channel_service = channel_service
        self.scheduler = AsyncIOScheduler()
    
    def start(self):
        """Start the scheduler."""
        logger.info("Starting usage reset scheduler...")
        
        # Schedule monthly reset on the 1st of each month at midnight
        self.scheduler.add_job(
            self._reset_all_usage,
            CronTrigger(day=1, hour=0, minute=0),
            id="reset_monthly_usage",
            name="Reset monthly channel usage",
            replace_existing=True
        )
        
        # Also schedule daily check for channels that need reset
        self.scheduler.add_job(
            self._check_and_reset,
            CronTrigger(hour=0, minute=30),
            id="check_usage_reset",
            name="Check and reset channel usage",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Usage reset scheduler started")
    
    async def _reset_all_usage(self):
        """Reset usage for all channels."""
        try:
            logger.info("Starting monthly usage reset for all channels")
            
            async with get_async_session() as session:
                # Get all active tenants
                query = text("""
                    SELECT DISTINCT tenant_id
                    FROM messaging.channels
                    WHERE deleted_at IS NULL
                        AND status IN ('active', 'pending')
                """)
                
                result = await session.execute(query)
                
                reset_count = 0
                for row in result:
                    await self.channel_service.reset_monthly_usage(row.tenant_id)
                    reset_count += 1
                
                logger.info(f"Reset monthly usage for {reset_count} tenants")
                
        except Exception as e:
            logger.error(f"Failed to reset monthly usage: {e}")
    
    async def _check_and_reset(self):
        """Check for channels that need usage reset."""
        try:
            # This handles edge cases where channels were created
            # mid-month or the scheduled reset was missed
            
            current_day = datetime.utcnow().day
            if current_day <= 3:  # Check first 3 days of month
                await self._reset_all_usage()
                
        except Exception as e:
            logger.error(f"Failed in usage check: {e}")
    
    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping usage reset scheduler...")
        self.scheduler.shutdown()
        logger.info("Usage reset scheduler stopped")