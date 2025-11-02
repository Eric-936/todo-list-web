"""
Pydantic schemas for Todo API request/response validation.
"""

from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

from app.models.todo import Priority


class TodoBase(BaseModel):
    """Base Todo schema with common fields."""
    
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="Todo title (1-200 characters)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Todo description (max 1000 characters)"
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Todo priority level"
    )
    due_date: Optional[date] = Field(
        None,
        description="Due date for the todo"
    )

    @validator('title')
    def title_must_not_be_empty(cls, v):
        """Ensure title is not just whitespace."""
        if not v or not v.strip():
            raise ValueError('Title cannot be empty or just whitespace')
        return v.strip()

    @validator('description')
    def description_strip_whitespace(cls, v):
        """Strip whitespace from description if provided."""
        return v.strip() if v else v


class TodoCreate(TodoBase):
    """Schema for creating new todos."""
    
    # All fields inherited from TodoBase
    # title is required, others are optional with defaults
    pass


class TodoUpdate(BaseModel):
    """Schema for updating todos - all fields optional for partial updates."""
    
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Todo title (1-200 characters)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Todo description (max 1000 characters)"
    )
    priority: Optional[Priority] = Field(
        None,
        description="Todo priority level"
    )
    due_date: Optional[date] = Field(
        None,
        description="Due date for the todo"
    )
    completed: Optional[bool] = Field(
        None,
        description="Whether the todo is completed"
    )

    @validator('title')
    def title_must_not_be_empty(cls, v):
        """Ensure title is not just whitespace if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Title cannot be empty or just whitespace')
        return v.strip() if v else v

    @validator('description')
    def description_strip_whitespace(cls, v):
        """Strip whitespace from description if provided."""
        return v.strip() if v else v


class TodoResponse(TodoBase):
    """Schema for Todo API responses."""
    
    id: int = Field(..., description="Todo ID")
    completed: bool = Field(default=False, description="Whether the todo is completed")
    created_at: datetime = Field(..., description="When the todo was created")
    updated_at: datetime = Field(..., description="When the todo was last updated")

    class Config:
        from_attributes = True  # For Pydantic v2 compatibility with SQLModel
    
    @classmethod
    def from_orm(cls, todo):
        """Create TodoResponse from Todo model instance."""
        return cls(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            priority=todo.priority,
            due_date=todo.due_date,
            completed=todo.completed,
            created_at=todo.created_at,
            updated_at=todo.updated_at
        )


class PaginationMeta(BaseModel):
    """Pagination metadata schema."""
    
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class TodoListResponse(BaseModel):
    """Schema for paginated todo list responses."""
    
    items: List[TodoResponse] = Field(..., description="List of todos")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class TodoStatsResponse(BaseModel):
    """Schema for todo statistics response."""
    
    total: int = Field(..., description="Total number of todos")
    completed: int = Field(..., description="Number of completed todos")
    pending: int = Field(..., description="Number of pending todos")
    overdue: int = Field(..., description="Number of overdue todos")
    by_priority: dict[str, int] = Field(..., description="Count by priority level")


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""
    
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Application version")
    checks: dict[str, Any] = Field(..., description="Individual component checks")
