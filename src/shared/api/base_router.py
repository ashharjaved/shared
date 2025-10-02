"""
Base FastAPI Router
Common router setup and utilities
"""
from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


def create_api_router(
    prefix: str,
    tags: Sequence[str],
    include_in_schema: bool = True,
) -> APIRouter:
    """
    Create a configured FastAPI router.
    
    Args:
        prefix: Route prefix (e.g., "/api/v1/users")
        tags: OpenAPI tags for grouping
        include_in_schema: Whether to include in OpenAPI schema
        
    Returns:
        Configured APIRouter instance
        
    Example:
        router = create_api_router(
            prefix="/api/v1/auth",
            tags=["Authentication"],
        )
    """
    router = APIRouter(
        prefix=prefix,
        tags=list(tags),  # Convert to list for FastAPI
        include_in_schema=include_in_schema,
    )
    
    logger.debug(
        f"Created API router: {prefix}",
        extra={"prefix": prefix, "tags": list(tags)},
    )
    
    return router