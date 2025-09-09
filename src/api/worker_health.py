from fastapi import APIRouter, Depends
from src.workers.manager import get_worker_manager

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("/health")
async def get_workers_health():
    """Get health status of all workers."""
    manager = await get_worker_manager()
    
    health_status = {}
    for worker_name, worker in manager.workers.items():
        if hasattr(worker, 'get_health_status'):
            health_status[worker_name] = worker.get_health_status()
        else:
            health_status[worker_name] = {
                "status": "running" if worker.is_running else "stopped"
            }
    
    return {
        "success": True,
        "data": health_status
    }


@router.get("/status")
async def get_workers_status():
    """Get status of all workers."""
    manager = await get_worker_manager()
    return {
        "success": True,
        "data": manager.get_worker_status()
    }


@router.post("/restart/{worker_name}")
async def restart_worker(worker_name: str):
    """Restart a specific worker."""
    manager = await get_worker_manager()
    
    if worker_name not in manager.workers:
        return {
            "success": False,
            "error": f"Worker {worker_name} not found"
        }
    
    # This would require more sophisticated worker management
    # For now, just return current status
    return {
        "success": True,
        "message": f"Worker {worker_name} restart requested"
    }