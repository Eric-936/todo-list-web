"""
Pytest tests for TodoService business logic.
"""

import time
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import Session, text

from app.database.database import create_db_and_tables, engine
from app.models.todo import Priority
from app.services.todo_service import PaginationResult, TodoFilters, TodoService


@pytest.fixture
def test_db():
    """Create test database session with cleanup."""
    create_db_and_tables()
    with Session(engine) as session:
        yield session
        # Clean up all todos after each test
        session.exec(text("DELETE FROM todo"))
        session.commit()


@pytest.fixture
def sample_todo_data():
    """Sample todo data for testing."""
    return {
        "title": "Test Todo",
        "description": "Test Description",
        "priority": Priority.MEDIUM,
        "due_date": date.today() + timedelta(days=7),
    }


@pytest.fixture
def created_todo(test_db, sample_todo_data):
    """Create a todo for testing."""
    return TodoService.create_todo(test_db, sample_todo_data)


class TestTodoFilters:
    """Test TodoFilters data class."""

    def test_limit_validation(self):
        """Test limit boundary validation."""
        filters = TodoFilters(limit=150)
        assert filters.limit == 100  # Max limit

        filters = TodoFilters(limit=0)
        assert filters.limit == 1  # Min limit

    def test_offset_validation(self):
        """Test offset validation."""
        filters = TodoFilters(offset=-5)
        assert filters.offset == 0  # No negative offset


class TestPaginationResult:
    """Test PaginationResult data class."""

    def test_pagination_calculation(self):
        """Test pagination calculations."""
        result = PaginationResult(items=[], total=23, limit=10, offset=0)
        assert result.total_pages == 3
        assert result.current_page == 1
        assert result.has_next is True
        assert result.has_prev is False

    def test_middle_page(self):
        """Test middle page calculations."""
        result = PaginationResult(items=[], total=50, limit=10, offset=20)
        assert result.current_page == 3
        assert result.has_next is True
        assert result.has_prev is True

    def test_last_page(self):
        """Test last page calculations."""
        result = PaginationResult(items=[], total=25, limit=10, offset=20)
        assert result.current_page == 3
        assert result.has_next is False
        assert result.has_prev is True


class TestCreateTodo:
    """Test TodoService.create_todo method."""

    def test_create_valid_todo(self, test_db, sample_todo_data):
        """Test creating a valid todo."""
        todo = TodoService.create_todo(test_db, sample_todo_data)

        assert todo.id is not None
        assert todo.title == "Test Todo"
        assert todo.description == "Test Description"
        assert todo.priority == Priority.MEDIUM
        assert todo.completed is False

    def test_create_invalid_todo(self, test_db):
        """Test creating todo with invalid data."""
        invalid_data = {"title": ""}  # Empty title should fail

        with pytest.raises(HTTPException) as exc_info:
            TodoService.create_todo(test_db, invalid_data)

        assert exc_info.value.status_code == 400


class TestGetTodoById:
    """Test TodoService.get_todo_by_id method."""

    def test_get_existing_todo(self, test_db, created_todo):
        """Test getting an existing todo."""
        todo = TodoService.get_todo_by_id(test_db, created_todo.id)

        assert todo.id == created_todo.id
        assert todo.title == created_todo.title

    def test_get_nonexistent_todo(self, test_db):
        """Test getting a non-existent todo."""
        with pytest.raises(HTTPException) as exc_info:
            TodoService.get_todo_by_id(test_db, 99999)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail


class TestGetTodos:
    """Test TodoService.get_todos method."""

    def test_get_all_todos(self, test_db):
        """Test getting all todos without filters."""
        # Create test data
        for i in range(5):
            TodoService.create_todo(test_db, {"title": f"Todo {i}"})

        filters = TodoFilters(limit=10, offset=0)
        result = TodoService.get_todos(test_db, filters)

        assert len(result.items) == 5
        assert result.total == 5
        assert isinstance(result, PaginationResult)

    def test_filter_by_completed(self, test_db):
        """Test filtering by completion status."""
        # Create completed and incomplete todos
        TodoService.create_todo(test_db, {"title": "Completed", "completed": True})
        TodoService.create_todo(test_db, {"title": "Incomplete", "completed": False})

        filters = TodoFilters(completed=True)
        result = TodoService.get_todos(test_db, filters)

        assert len(result.items) == 1
        assert result.items[0].completed is True

    def test_search_functionality(self, test_db):
        """Test search in title and description."""
        TodoService.create_todo(
            test_db, {"title": "Important Task", "description": "Very important"}
        )
        TodoService.create_todo(
            test_db, {"title": "Normal Task", "description": "Regular task"}
        )

        filters = TodoFilters(search="important")
        result = TodoService.get_todos(test_db, filters)

        assert len(result.items) == 1
        assert "Important" in result.items[0].title


class TestUpdateTodo:
    """Test TodoService.update_todo method."""

    def test_update_single_field(self, test_db, created_todo):
        """Test updating a single field."""
        update_data = {"title": "Updated Title"}
        updated_todo = TodoService.update_todo(test_db, created_todo.id, update_data)

        assert updated_todo.title == "Updated Title"
        assert updated_todo.description == created_todo.description  # Unchanged

    def test_update_multiple_fields(self, test_db, created_todo):
        """Test updating multiple fields."""
        update_data = {
            "title": "New Title",
            "completed": True,
            "priority": Priority.HIGH,
        }
        updated_todo = TodoService.update_todo(test_db, created_todo.id, update_data)

        assert updated_todo.title == "New Title"
        assert updated_todo.completed is True
        assert updated_todo.priority == Priority.HIGH

    def test_update_nonexistent_todo(self, test_db):
        """Test updating non-existent todo."""
        with pytest.raises(HTTPException) as exc_info:
            TodoService.update_todo(test_db, 99999, {"title": "New Title"})

        assert exc_info.value.status_code == 404


class TestDeleteTodo:
    """Test TodoService.delete_todo method."""

    def test_delete_existing_todo(self, test_db, created_todo):
        """Test deleting an existing todo."""
        result = TodoService.delete_todo(test_db, created_todo.id)

        assert "deleted successfully" in result["message"]

        # Verify todo is deleted
        with pytest.raises(HTTPException):
            TodoService.get_todo_by_id(test_db, created_todo.id)

    def test_delete_nonexistent_todo(self, test_db):
        """Test deleting non-existent todo."""
        with pytest.raises(HTTPException) as exc_info:
            TodoService.delete_todo(test_db, 99999)

        assert exc_info.value.status_code == 404