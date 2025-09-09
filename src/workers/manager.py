import asyncio
import signal
from typing import Dict, List, Optional

import structlog
from fastapi import FastAPI

from src.workers.base_worker import BaseWorker
from src.workers.partition_worker import PartitionWorker
from src.workers.session_cleanup_worker import SessionCleanupWorker
from src.workers.health_check_worker import HealthCheckWorker

logger = structlog.get_logger()


class WorkerManager:
    """Manager for all background workers."""
    
    def __init__(self, app: Optional[FastAPI] = None):
        self.app = app
        self.workers: Dict[str, BaseWorker] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.shutdown_event = asyncio.Event()
    
    def register_worker(self, worker: BaseWorker) -> None:
        """Register a worker with the manager."""
        self.workers[worker.worker_name] = worker
        logger.info(f"Registered worker: {worker.worker_name}")
    
    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))
    
    async def start_all(self) -> None:
        """Start all registered workers."""
        self.setup_signal_handlers()
        
        logger.info(f"Starting {len(self.workers)} workers")
        
        for worker_name, worker in self.workers.items():
            try:
                task = asyncio.create_task(worker.run(), name=f"worker_{worker_name}")
                self.tasks[worker_name] = task
                logger.info(f"Started worker: {worker_name}")
                
                # Small delay between worker starts
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to start worker {worker_name}: {str(e)}")
    
    async def shutdown(self) -> None:
        """Graceful shutdown of all workers."""
        logger.info("Initiating worker shutdown")
        self.shutdown_event.set()
        
        # Request all workers to shutdown
        for worker_name, worker in self.workers.items():
            try:
                await worker.shutdown()
            except Exception as e:
                logger.error(f"Error during worker {worker_name} shutdown: {str(e)}")
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        
        logger.info("All workers shutdown complete")
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()
    
    def get_worker_status(self) -> Dict[str, str]:
        """Get status of all workers."""
        status = {}
        for worker_name, worker in self.workers.items():
            status[worker_name] = "running" if worker.is_running else "stopped"
        return status


# Default worker setup
def create_default_worker_manager(app: Optional[FastAPI] = None) -> WorkerManager:
    """Create a worker manager with default workers."""
    manager = WorkerManager(app)
    
    # Register default workers
    manager.register_worker(PartitionWorker())
    manager.register_worker(SessionCleanupWorker())
    manager.register_worker(HealthCheckWorker())
    
    return manager


# Global worker manager instance
worker_manager: Optional[WorkerManager] = None


async def get_worker_manager() -> WorkerManager:
    """Get the global worker manager instance."""
    global worker_manager
    if worker_manager is None:
        worker_manager = create_default_worker_manager()
    return worker_manager