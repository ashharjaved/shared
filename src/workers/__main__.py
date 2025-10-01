# #!/usr/bin/env python3
# """CLI entry points for workers."""

# import asyncio
# import argparse
# import sys

# from src.workers.manager import create_default_worker_manager
# from src.workers.partition_worker import PartitionWorker
# from src.workers.session_cleanup_worker import SessionCleanupWorker
# from src.workers.health_check_worker import HealthCheckWorker


# async def run_all_workers():
#     """Run all workers together."""
#     manager = create_default_worker_manager()
#     await manager.start_all()
#     await manager.wait_for_shutdown()


# async def run_single_worker(worker_name: str):
#     """Run a single worker."""
#     if worker_name == "partition":
#         worker = PartitionWorker()
#     elif worker_name == "session_cleanup":
#         worker = SessionCleanupWorker()
#     elif worker_name == "health_check":
#         worker = HealthCheckWorker()
#     else:
#         print(f"Unknown worker: {worker_name}")
#         return
    
#     await worker.run()


# def main():
#     """Main CLI entry point."""
#     parser = argparse.ArgumentParser(description="WhatsApp Chatbot Platform Workers")
#     parser.add_argument(
#         "worker",
#         nargs="?",
#         choices=["all", "partition", "session_cleanup", "health_check"],
#         default="all",
#         help="Which worker to run (default: all)"
#     )
    
#     args = parser.parse_args()
    
#     try:
#         if args.worker == "all":
#             asyncio.run(run_all_workers())
#         else:
#             asyncio.run(run_single_worker(args.worker))
#     except KeyboardInterrupt:
#         print("\nShutting down workers...")
#     except Exception as e:
#         print(f"Error: {e}")
#         sys.exit(1)


# if __name__ == "__main__":
#     main()