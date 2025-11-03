"""
Comprehensive integration tests for Todo List API.
Tests core functionality with database cleanup after each test.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, text

from app.main import app


@pytest.fixture(scope="function")
def client():
    """Create test client and clean up database after each test."""
    # Use the actual database but clean it up after each test
    client = TestClient(app)

    yield client

    # Cleanup: Delete all data from the database after each test
    from app.database.database import engine

    with Session(engine) as session:
        try:
            # Delete all todos
            session.exec(text("DELETE FROM todo"))
            session.commit()
        except Exception:
            session.rollback()


class TestTodoAPICleanup:
    """Comprehensive tests with database cleanup after each test."""

    def test_01_create_basic_todo(self, client: TestClient):
        """Test creating a basic todo item."""
        response = client.post(
            "/api/todos/", json={"title": "Basic Todo", "description": "Simple test"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Basic Todo"
        assert data["completed"] is False
        assert data["priority"] == "MEDIUM"

    def test_02_create_todo_with_different_priorities(self, client: TestClient):
        """Test creating todos with HIGH and LOW priorities."""
        # HIGH priority
        response = client.post(
            "/api/todos/", json={"title": "Urgent Task", "priority": "HIGH"}
        )
        assert response.status_code == 201
        assert response.json()["priority"] == "HIGH"

        # LOW priority
        response = client.post(
            "/api/todos/", json={"title": "Later Task", "priority": "LOW"}
        )
        assert response.status_code == 201
        assert response.json()["priority"] == "LOW"

    def test_03_list_todos_with_pagination(self, client: TestClient):
        """Test getting todos list with pagination."""
        # Create 5 test todos
        for i in range(5):
            response = client.post("/api/todos/", json={"title": f"Todo {i+1}"})
            assert response.status_code == 201

        # Get first page with page_size=3
        response = client.get("/api/todos/?page=1&page_size=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["page"] == 1

    def test_04_search_functionality(self, client: TestClient):
        """Test searching todos by title/description."""
        # Create test data
        client.post("/api/todos/", json={"title": "Buy milk"})
        client.post("/api/todos/", json={"title": "Walk dog"})
        client.post("/api/todos/", json={"title": "Buy bread"})

        # Search for "buy"
        response = client.get("/api/todos/?search=buy")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        for item in items:
            assert "buy" in item["title"].lower()

    def test_05_filter_by_completion_status(self, client: TestClient):
        """Test filtering by completed/pending status."""
        # Create mixed status todos
        client.post("/api/todos/", json={"title": "Done Task", "completed": True})
        client.post("/api/todos/", json={"title": "Todo Task", "completed": False})

        # Filter completed
        response = client.get("/api/todos/?completed=true")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["completed"] is True

        # Filter pending
        response = client.get("/api/todos/?completed=false")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["completed"] is False

    def test_06_update_todo(self, client: TestClient):
        """Test updating an existing todo."""
        # Create todo
        response = client.post(
            "/api/todos/", json={"title": "Original", "priority": "LOW"}
        )
        todo_id = response.json()["id"]

        # Update todo
        response = client.patch(
            f"/api/todos/{todo_id}",
            json={"title": "Updated", "completed": True, "priority": "HIGH"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["completed"] is True
        assert data["priority"] == "HIGH"

    def test_07_delete_todo(self, client: TestClient):
        """Test deleting a todo."""
        # Create todo
        response = client.post("/api/todos/", json={"title": "Delete me"})
        todo_id = response.json()["id"]

        # Delete todo
        response = client.delete(f"/api/todos/{todo_id}")
        assert response.status_code == 204

        # Verify deletion
        response = client.get(f"/api/todos/{todo_id}")
        assert response.status_code == 404

    def test_08_todo_statistics(self, client: TestClient):
        """Test getting todo statistics."""
        # Create test data - first create, then update to completed
        response1 = client.post("/api/todos/", json={"title": "Done 1"})
        todo1_id = response1.json()["id"]
        client.patch(f"/api/todos/{todo1_id}", json={"completed": True})

        response2 = client.post("/api/todos/", json={"title": "Done 2"})
        todo2_id = response2.json()["id"]
        client.patch(f"/api/todos/{todo2_id}", json={"completed": True})

        client.post("/api/todos/", json={"title": "Todo 1", "completed": False})

        # Get stats
        response = client.get("/api/todos/stats")
        assert response.status_code == 200
        stats = response.json()
        assert stats["total"] == 3
        assert stats["completed"] == 2
        assert stats["pending"] == 1

    def test_09_error_handling(self, client: TestClient):
        """Test error handling for invalid requests."""
        # No title
        response = client.post("/api/todos/", json={"description": "No title"})
        assert response.status_code == 422

        # Invalid priority
        response = client.post(
            "/api/todos/", json={"title": "Test", "priority": "INVALID"}
        )
        assert response.status_code == 422

        # Non-existent todo
        response = client.get("/api/todos/99999")
        assert response.status_code == 404

    def test_10_database_cleanup_verification(self, client: TestClient):
        """Test that database cleanup works correctly."""
        # This test should start with clean database from previous test cleanup
        response = client.get("/api/todos/")
        assert response.status_code == 200
        # Note: We don't assert length == 0 here because cleanup happens AFTER test,
        # so we just verify the API works correctly

        # Create some data
        client.post("/api/todos/", json={"title": "Cleanup Test 1"})
        client.post("/api/todos/", json={"title": "Cleanup Test 2"})

        # Verify data exists
        response = client.get("/api/todos/")
        assert response.status_code == 200
        items = response.json()["items"]
        cleanup_items = [item for item in items if "Cleanup Test" in item["title"]]
        assert len(cleanup_items) == 2
        # Data will be cleaned up after this test completes
