"""Worker for checking template approval status."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from src.messaging.application.services.template_service import TemplateService
from messaging.domain.entities.message_template import TemplateStatus
from src.shared_.database import get_async_session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class TemplateStatusChecker:
    """Worker for checking template approval status."""
    
    def __init__(
        self,
        template_service: TemplateService,
        check_interval_minutes: int = 30
    ):
        self.template_service = template_service
        self.check_interval = check_interval_minutes * 60
        self.running = False
    
    async def start(self):
        """Start the status checker."""
        logger.info("Starting template status checker...")
        self.running = True
        
        while self.running:
            try:
                await self._check_pending_templates()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Status checker error: {e}")
                await asyncio.sleep(60)  # Wait a minute on error
    
    async def _check_pending_templates(self):
        """Check status of pending templates."""
        try:
            # Get pending templates older than 5 minutes
            cutoff = datetime.utcnow() - timedelta(minutes=5)
            
            async with get_async_session() as session:
                query = text("""
                    SELECT DISTINCT
                        t.id,
                        t.tenant_id
                    FROM messaging.message_templates t
                    WHERE t.status = 'pending'
                        AND t.submitted_at < :cutoff
                        AND t.whatsapp_template_id IS NOT NULL
                    LIMIT 50
                """)
                
                result = await session.execute(query, {"cutoff": cutoff})
                
                templates = []
                for row in result:
                    templates.append({
                        "id": row.id,
                        "tenant_id": row.tenant_id
                    })
                
                if templates:
                    logger.info(f"Checking status for {len(templates)} pending templates")
                    
                    for template in templates:
                        await self.template_service.check_approval_status(
                            template_id=template["id"],
                            tenant_id=template["tenant_id"]
                        )
                        
                        # Small delay between checks
                        await asyncio.sleep(1)
                        
        except Exception as e:
            logger.error(f"Failed to check pending templates: {e}")
    
    def stop(self):
        """Stop the status checker."""
        logger.info("Stopping template status checker...")
        self.running = False