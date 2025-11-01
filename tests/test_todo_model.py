"""
Comprehensive tests for Todo model.
"""

import pytest
import time
from datetime import datetime, date, timezone, timedelta
from pydantic import ValidationError
from sqlmodel import Session, select
from app.models.todo import Todo, Priority, EST, est_now
from app.database.database import engine, create_db_and_tables


# Basic Model Creation Tests

def test_create_todo_complete():
    """Test creating todo with all fields."""
    due_date = date(2025, 12, 31)
    todo = Todo(
        title="Complete Todo",
        description="A todo with all fields",
        priority=Priority.HIGH,
        due_date=due_date,
        completed=True
    )
    
    assert todo.title == "Complete Todo"
    assert todo.description == "A todo with all fields"
    assert todo.priority == Priority.HIGH
    assert todo.due_date == due_date
    assert todo.completed is True


def test_auto_timestamps():
    """Test automatic timestamp generation."""
    before = est_now()
    todo = Todo(title="Timestamp Test")
    after = est_now()
    
    # Check timestamps are in EST and reasonable
    assert todo.created_at.tzinfo == EST
    assert todo.updated_at.tzinfo == EST
    assert before <= todo.created_at <= after
    assert before <= todo.updated_at <= after


# Field Validation Tests
def test_title_required():
    """Test that title is required."""
    with pytest.raises(ValueError):
        Todo()  # No title provided


def test_title_length_validation():
    """Test title length constraints."""
    # Valid lengths
    Todo(title="A")  # minimum 1 char
    Todo(title="A" * 200)  # maximum 200 chars
    
    # Invalid lengths
    with pytest.raises(ValidationError):
        Todo(title="")  # empty string
    
    with pytest.raises(ValidationError):
        Todo(title="A" * 201)  # too long


def test_description_length_validation():
    """Test description length constraints."""
    # Valid lengths
    Todo(title="Test", description=None)  # None is valid
    Todo(title="Test", description="")  # empty string is valid
    Todo(title="Test", description="A" * 1000)  # maximum 1000 chars
    
    # Invalid length
    with pytest.raises(ValidationError):
        Todo(title="Test", description="A" * 1001)  # too long


def test_priority_validation():
    """Test priority enum validation."""
    # Valid priorities
    for priority in Priority:
        todo = Todo(title="Test", priority=priority)
        assert todo.priority == priority
    
    # Invalid priority
    with pytest.raises(ValidationError):
        Todo(title="Test", priority="INVALID")


# Business Methods Tests
def test_mark_completed():
    """Test marking todo as completed."""
    todo = Todo(title="Test")
    original_updated = todo.updated_at
    
    time.sleep(0.01)  # Small delay to ensure timestamp changes
    todo.mark_completed()
    
    assert todo.completed is True
    assert todo.updated_at > original_updated
    assert todo.updated_at.tzinfo == EST


def test_mark_incomplete():
    """Test marking todo as incomplete."""
    todo = Todo(title="Test", completed=True)
    original_updated = todo.updated_at
    
    time.sleep(0.01)
    todo.mark_incomplete()
    
    assert todo.completed is False
    assert todo.updated_at > original_updated
    assert todo.updated_at.tzinfo == EST


def test_repr_method():
    """Test string representation."""
    # Incomplete todo
    todo = Todo(title="Test Todo", priority=Priority.HIGH)
    repr_str = repr(todo)
    assert "Test Todo" in repr_str
    assert "HIGH" in repr_str
    assert "⏳" in repr_str  # incomplete emoji
    
    # Completed todo
    todo.mark_completed()
    repr_str = repr(todo)
    assert "✅" in repr_str  # completed emoji


# Timezone Tests
def test_est_timezone_function():
    """Test EST timezone helper function."""
    now_est = est_now()
    
    assert now_est.tzinfo == EST
    assert EST.utcoffset(None) == timedelta(hours=-5)


def test_future_due_date():
    """Test todos with future due dates."""
    future_date = date(2030, 1, 1)
    todo = Todo(title="Future Todo", due_date=future_date)
    
    assert todo.due_date == future_date


# Database Integration Tests
@pytest.fixture
def setup_database():
    """Set up database for tests."""
    create_db_and_tables()
    yield


def test_save_and_retrieve_todo(setup_database):
    """Test saving and retrieving todo from database."""
    with Session(engine) as session:
        # Create and save todo
        todo = Todo(
            title="Database Test",
            description="Testing database operations",
            priority=Priority.HIGH,
            due_date=date(2025, 12, 31)
        )
        
        session.add(todo)
        session.commit()
        session.refresh(todo)
        
        # Should have an ID now
        assert todo.id is not None
        todo_id = todo.id
        
        # Retrieve from database
        retrieved_todo = session.get(Todo, todo_id)
        
        assert retrieved_todo is not None
        assert retrieved_todo.title == "Database Test"
        assert retrieved_todo.description == "Testing database operations"
        assert retrieved_todo.priority == Priority.HIGH
        assert retrieved_todo.due_date == date(2025, 12, 31)
        assert retrieved_todo.completed is False


def test_update_todo_in_database(setup_database):
    """Test updating todo in database."""
    with Session(engine) as session:
        # Create and save todo
        todo = Todo(title="Update Test")
        session.add(todo)
        session.commit()
        session.refresh(todo)
        
        todo_id = todo.id
        original_updated = todo.updated_at
        
        # Update the todo
        time.sleep(0.01)
        todo.mark_completed()
        session.add(todo)
        session.commit()
        
        # Retrieve updated todo
        updated_todo = session.get(Todo, todo_id)
        
        assert updated_todo.completed is True
        assert updated_todo.updated_at > original_updated


def test_query_todos_by_criteria(setup_database):
    """Test querying todos by various criteria."""
    with Session(engine) as session:
        # Create test data
        todos = [
            Todo(title="High Priority", priority=Priority.HIGH),
            Todo(title="Completed Task", completed=True),
            Todo(title="Due Soon", due_date=date(2025, 12, 1)),
            Todo(title="Low Priority", priority=Priority.LOW)
        ]
        
        for todo in todos:
            session.add(todo)
        session.commit()
        
        # Query by completion status
        completed = session.exec(
            select(Todo).where(Todo.completed == True)
        ).all()
        assert len(completed) >= 1
        assert any(t.title == "Completed Task" for t in completed)
        
        # Query by priority
        high_priority = session.exec(
            select(Todo).where(Todo.priority == Priority.HIGH)
        ).all()
        assert len(high_priority) >= 1
        assert any(t.title == "High Priority" for t in high_priority)
        
        # Query by due date
        with_due_date = session.exec(
            select(Todo).where(Todo.due_date.is_not(None))
        ).all()
        assert len(with_due_date) >= 1
        assert any(t.title == "Due Soon" for t in with_due_date)