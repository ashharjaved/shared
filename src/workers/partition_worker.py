# import datetime
# from typing import List
# from uuid import UUID

# import structlog
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from src.workers.base_worker import BaseWorker
# from shared.database.database import get_db

# logger = structlog.get_logger()


# class PartitionWorker(BaseWorker):
#     """Worker for managing database partitions."""
    
#     def __init__(self):
#         super().__init__(
#             worker_name="partition_manager",
#             interval=3600,  # Run hourly
#             batch_size=1
#         )
    
#     async def execute(self) -> bool:
#         """Create partitions for upcoming months."""
#         try:
#             async with get_db_session() as session:
#                 # Create partitions for current month and next month
#                 success = await self.create_monthly_partitions(session)
#                 if not success:
#                     return False
                
#                 # Clean up old partitions (optional)
#                 await self.cleanup_old_partitions(session)
                
#             return True
#         except Exception as e:
#             logger.error(f"Partition worker failed: {str(e)}", exc_info=True)
#             return False
    
#     async def create_monthly_partitions(self, session: AsyncSession) -> bool:
#         """Create monthly partitions for partitioned tables."""
#         try:
#             # Get current and next month
#             now = datetime.datetime.utcnow()
#             current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#             next_month = (current_month + datetime.timedelta(days=32)).replace(day=1)
            
#             # Create partitions for each partitioned table
#             tables = ["messages", "outbox_events", "webhook_events"]
            
#             for table_name in tables:
#                 # Create current month partition if it doesn't exist
#                 await self.create_partition_if_not_exists(
#                     session, table_name, current_month
#                 )
                
#                 # Create next month partition
#                 await self.create_partition_if_not_exists(
#                     session, table_name, next_month
#                 )
            
#             logger.info(
#                 "Monthly partitions created successfully",
#                 tables=tables,
#                 current_month=current_month.isoformat(),
#                 next_month=next_month.isoformat()
#             )
#             return True
            
#         except Exception as e:
#             logger.error(f"Failed to create monthly partitions: {str(e)}", exc_info=True)
#             return False
    
#     async def create_partition_if_not_exists(
#         self,
#         session: AsyncSession,
#         table_name: str,
#         month: datetime.datetime
#     ) -> bool:
#         """Create a partition for a specific month if it doesn't exist."""
#         partition_name = f"{table_name}_{month.strftime('%Y_%m')}"
#         start_date = month
#         end_date = (month + datetime.timedelta(days=32)).replace(day=1)
        
#         # Check if partition already exists
#         check_sql = text("""
#             SELECT EXISTS (
#                 SELECT FROM information_schema.tables 
#                 WHERE table_name = :partition_name
#             )
#         """)
        
#         result = await session.execute(check_sql, {"partition_name": partition_name})
#         exists = result.scalar()
        
#         if exists:
#             logger.debug(f"Partition {partition_name} already exists")
#             return True
        
#         # Create partition
#         create_sql = text(f"""
#             CREATE TABLE {partition_name} PARTITION OF {table_name}
#             FOR VALUES FROM ('{start_date.isoformat()}') TO ('{end_date.isoformat()}');
#         """)
        
#         try:
#             await session.execute(create_sql)
#             await session.commit()
            
#             # Create indexes on the new partition
#             await self.create_partition_indexes(session, table_name, partition_name)
            
#             logger.info(f"Created partition {partition_name}")
#             return True
            
#         except Exception as e:
#             await session.rollback()
#             logger.error(f"Failed to create partition {partition_name}: {str(e)}")
#             return False
    
#     async def create_partition_indexes(
#         self,
#         session: AsyncSession,
#         table_name: str,
#         partition_name: str
#     ):
#         """Create indexes on a new partition."""
#         index_sqls = []
        
#         if table_name == "messages":
#             index_sqls = [
#                 f"CREATE INDEX ON {partition_name} (tenant_id)",
#                 f"CREATE INDEX ON {partition_name} (channel_id)",
#                 f"CREATE INDEX ON {partition_name} (created_at)",
#                 f"CREATE INDEX ON {partition_name} (status)",
#             ]
#         elif table_name == "outbox_events":
#             index_sqls = [
#                 f"CREATE INDEX ON {partition_name} (tenant_id)",
#                 f"CREATE INDEX ON {partition_name} (status)",
#                 f"CREATE INDEX ON {partition_name} (not_before)",
#                 f"CREATE INDEX ON {partition_name} (created_at)",
#             ]
#         elif table_name == "webhook_events":
#             index_sqls = [
#                 f"CREATE INDEX ON {partition_name} (tenant_id)",
#                 f"CREATE INDEX ON {partition_name} (provider)",
#                 f"CREATE INDEX ON {partition_name} (created_at)",
#                 f"CREATE INDEX ON {partition_name} (processed_at)",
#             ]
        
#         for index_sql in index_sqls:
#             try:
#                 await session.execute(text(index_sql))
#             except Exception as e:
#                 logger.warning(f"Failed to create index: {index_sql}: {str(e)}")
    
#     async def cleanup_old_partitions(self, session: AsyncSession, retention_months: int = 12):
#         """Clean up partitions older than retention period."""
#         try:
#             cutoff_date = (datetime.datetime.utcnow() - 
#                           datetime.timedelta(days=retention_months * 30)).replace(day=1)
            
#             # Get all partitions for each table
#             tables = ["messages", "outbox_events", "webhook_events"]
            
#             for table_name in tables:
#                 # Find old partitions
#                 find_sql = text("""
#                     SELECT table_name FROM information_schema.tables 
#                     WHERE table_name LIKE :pattern
#                     AND table_name != :main_table
#                 """)
                
#                 result = await session.execute(
#                     find_sql, 
#                     {"pattern": f"{table_name}_%", "main_table": table_name}
#                 )
                
#                 partitions = [row[0] for row in result]
                
#                 for partition in partitions:
#                     # Extract date from partition name
#                     try:
#                         year_month = partition.split('_')[-2:]
#                         partition_date = datetime.datetime(
#                             int(year_month[0]), int(year_month[1]), 1
#                         )
                        
#                         if partition_date < cutoff_date:
#                             # Drop old partition
#                             drop_sql = text(f"DROP TABLE {partition}")
#                             await session.execute(drop_sql)
#                             logger.info(f"Dropped old partition: {partition}")
                            
#                     except (ValueError, IndexError):
#                         logger.warning(f"Could not parse date from partition: {partition}")
#                         continue
            
#             await session.commit()
            
#         except Exception as e:
#             await session.rollback()
#             logger.error(f"Failed to cleanup old partitions: {str(e)}")