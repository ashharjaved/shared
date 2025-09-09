import datetime
import socket
from typing import Dict, Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.workers.base_worker import BaseWorker
from shared.database.database import get_db_session
from src.shared.redis import get_redis

logger = structlog.get_logger()


class HealthCheckWorker(BaseWorker):
    """Worker for performing system health checks."""
    
    def __init__(self):
        super().__init__(
            worker_name="health_check",
            interval=60,  # Run every minute
            batch_size=1
        )
        self.health_status: Dict[str, Any] = {}
    
    async def execute(self) -> bool:
        """Perform comprehensive health checks."""
        try:
            health_checks = {
                "database": await self.check_database(),
                "redis": await self.check_redis(),
                "network": await self.check_network(),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
            
            # Update health status
            self.health_status = health_checks
            
            # Log overall status
            all_healthy = all(check["healthy"] for check in health_checks.values() 
                            if isinstance(check, dict) and "healthy" in check)
            
            if all_healthy:
                logger.info("All health checks passed", checks=health_checks)
            else:
                logger.warning("Some health checks failed", checks=health_checks)
            
            return all_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            return False
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = datetime.datetime.utcnow()
            
            async with get_db_session() as session:
                # Simple query to check connectivity
                result = await session.execute(text("SELECT 1"))
                row = result.scalar()
                
                duration = (datetime.datetime.utcnow() - start_time).total_seconds()
                
                if row == 1:
                    return {
                        "healthy": True,
                        "response_time": duration,
                        "message": "Database connection successful"
                    }
                else:
                    return {
                        "healthy": False,
                        "response_time": duration,
                        "message": "Database query returned unexpected result"
                    }
                    
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Database connection failed: {str(e)}"
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance."""
        try:
            start_time = datetime.datetime.utcnow()
            
            redis = await get_redis()
            pong = await redis.ping()
            
            duration = (datetime.datetime.utcnow() - start_time).total_seconds()
            
            if pong:
                return {
                    "healthy": True,
                    "response_time": duration,
                    "message": "Redis connection successful"
                }
            else:
                return {
                    "healthy": False,
                    "response_time": duration,
                    "message": "Redis ping failed"
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Redis connection failed: {str(e)}"
            }
    
    async def check_network(self) -> Dict[str, Any]:
        """Check basic network connectivity."""
        try:
            # Check DNS resolution
            socket.gethostbyname("google.com")
            
            return {
                "healthy": True,
                "message": "Network connectivity OK"
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Network check failed: {str(e)}"
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return self.health_status