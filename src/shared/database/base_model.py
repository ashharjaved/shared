# src/shared/database/base_model.py
"""
Base ORM model with common patterns.
"""

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

class BaseModel(AsyncAttrs, DeclarativeBase):
    """Base model for all ORM entities."""
    