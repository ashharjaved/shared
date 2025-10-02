"""
Standard API Response Models
Consistent response structure across all endpoints
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """
    Error detail structure for API responses.
    
    Attributes:
        code: Machine-readable error code
        message: Human-readable error message
        details: Additional error context (optional)
    """
    
    model_config = ConfigDict(frozen=True)
    
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        None,
        description="Additional error context",
    )


class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response wrapper.
    
    Attributes:
        success: Always True for success responses
        data: Response payload
        message: Optional success message
    """
    
    model_config = ConfigDict(frozen=True)
    
    success: bool = Field(True, description="Indicates successful operation")
    data: T = Field(..., description="Response payload")
    message: str | None = Field(None, description="Optional success message")


class ErrorResponse(BaseModel):
    """
    Standard error response wrapper.
    
    Always returned for error cases (4xx, 5xx).
    """
    
    model_config = ConfigDict(extra="forbid")
    
    error: ErrorDetail

class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated response wrapper.
    
    Attributes:
        success: Always True
        data: List of items
        total: Total number of items (across all pages)
        page: Current page number (1-indexed)
        page_size: Items per page
        total_pages: Total number of pages
    """
    
    model_config = ConfigDict(frozen=True)
    
    success: bool = Field(True, description="Indicates successful operation")
    data: list[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")