"""
SQLModel database model for Todo items.
"""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from sqlmodel import Field, SQLModel


# EST timezone (UTC-5)
EST = timezone(timedelta(hours=-5))


def est_now() -> datetime:
    """Get current time in EST timezone."""
    return datetime.now(EST)


class Priority(str, Enum):
    """Todo priority levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Todo(SQLModel, table=True):
    """
    Todo model for database and API.

    This single class serves as both:
    - Database table
    - API schema
    """

    # Model configuration
    model_config = {
        "validate_assignment": True,
        "validate_default": True,
        "str_strip_whitespace": True,
        "use_enum_values": True,
    }

    # Primary key
    id: int | None = Field(default=None, primary_key=True)

    # Required fields
    title: str = Field(
        min_length=1, max_length=200, description="Todo title (1-200 characters)"
    )

    # Optional fields
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Todo description (max 1000 characters)",
    )

    priority: Priority = Field(
        default=Priority.MEDIUM, description="Todo priority level"
    )

    due_date: date | None = Field(default=None, description="Due date for the todo")

    completed: bool = Field(default=False, description="Whether the todo is completed")

    # Auto-managed timestamps
    created_at: datetime = Field(
        default_factory=est_now, description="When the todo was created"
    )

    updated_at: datetime = Field(
        default_factory=est_now, description="When the todo was last updated"
    )

    def __init__(self, **data):
        """For title requirement"""
        if "title" not in data:
            raise ValueError("title field is required")
        super().__init__(**data)

    def __repr__(self) -> str:
        """String representation for debugging."""
        status = "✅" if self.completed else "⏳"
        return f"<Todo {self.id}: {status} [{self.priority}] {self.title}>"

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = est_now()
