# import asyncio
# import signal
# import time
# from abc import ABC, abstractmethod
# from typing import Optional

# import structlog
# from redis.asyncio import Redis

# from src.shared.config import settings
# from shared.database.database import get_db_session
# from src.shared.redis import get_redis

# logger = structlog.get_logger()


# class BaseWorker(ABC):
#     """Base class for all background workers."""
    
#     def __init__(
#         self,
#         worker_name: str,
#         interval: int = 60,
#         batch_size: int = 100,
#         max_retries: int = 3
#     ):
#         self.worker_name = worker_name
#         self.interval = interval
#         self.batch_size = batch_size
#         self.max_retries = max_retries
#         self.is_running = False
#         self.redis: Optional[Redis] = None
#         self.shutdown_event = asyncio.Event()
    
#     async def initialize(self):
#         """Initialize worker resources."""
#         try:
#             self.redis = await get_redis()
#             logger.info(f"Worker {self.worker_name} initialized successfully")
#         except Exception as e:
#             logger.error(f"Failed to initialize worker {self.worker_name}: {str(e)}")
#             raise
    
#     async def shutdown(self):
#         """Graceful shutdown of worker."""
#         self.is_running = False
#         self.shutdown_event.set()
#         logger.info(f"Worker {self.worker_name} shutting down")
    
#     def setup_signal_handlers(self):
#         """Setup signal handlers for graceful shutdown."""
#         for sig in [signal.SIGINT, signal.SIGTERM]:
#             signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))
    
#     async def run(self):
#         """Main worker loop."""
#         await self.initialize()
#         self.setup_signal_handlers()
#         self.is_running = True
        
#         logger.info(f"Worker {self.worker_name} started with interval {self.interval}s")
        
#         while self.is_running and not self.shutdown_event.is_set():
#             try:
#                 start_time = time.time()
                
#                 # Execute the worker task
#                 success = await self.execute()
                
#                 duration = time.time() - start_time
#                 if success:
#                     logger.info(
#                         f"Worker {self.worker_name} completed successfully",
#                         duration=duration,
#                         batch_size=self.batch_size
#                     )
#                 else:
#                     logger.warning(
#                         f"Worker {self.worker_name} completed with errors",
#                         duration=duration
#                     )
                
#                 # Wait for next interval, but check for shutdown frequently
#                 await asyncio.wait_for(
#                     self.shutdown_event.wait(),
#                     timeout=self.interval
#                 )
                
#             except asyncio.TimeoutError:
#                 # Normal case - continue with next iteration
#                 pass
#             except asyncio.CancelledError:
#                 logger.info(f"Worker {self.worker_name} cancelled")
#                 break
#             except Exception as e:
#                 logger.error(
#                     f"Worker {self.worker_name} failed with error: {str(e)}",
#                     exc_info=True
#                 )
#                 # Wait before retrying on error
#                 await asyncio.sleep(min(300, self.interval * 2))
        
#         logger.info(f"Worker {self.worker_name} stopped")
    
#     @abstractmethod
#     async def execute(self) -> bool:
#         """Execute the worker's main task. Must be implemented by subclasses."""
#         pass
    
#     async def acquire_lock(self, lock_key: str, ttl: int = 300) -> bool:
#         """Acquire a distributed lock using Redis."""
#         try:
#             acquired = await self.redis.set(
#                 lock_key,
#                 self.worker_name,
#                 ex=ttl,
#                 nx=True  # Only set if not exists
#             )
#             return acquired is not None
#         except Exception as e:
#             logger.error(f"Failed to acquire lock {lock_key}: {str(e)}")
#             return False
    
#     async def release_lock(self, lock_key: str) -> bool:
#         """Release a distributed lock."""
#         try:
#             # Only release if we own the lock
#             current_owner = await self.redis.get(lock_key)
#             if current_owner == self.worker_name:
#                 await self.redis.delete(lock_key)
#                 return True
#             return False
#         except Exception as e:
#             logger.error(f"Failed to release lock {lock_key}: {str(e)}")
#             return False
    
#     async def with_lock(self, lock_key: str, ttl: int = 300):
#         """Context manager for distributed locks."""
#         acquired = await self.acquire_lock(lock_key, ttl)
#         if not acquired:
#             raise Exception(f"Failed to acquire lock: {lock_key}")
        
#         try:
#             yield
#         finally:
#             await self.release_lock(lock_key)