# tests/test_basic.py - 基本的API测试

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz_endpoint():
    """测试简单健康检查"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_create_todo():
    """测试创建待办事项"""
    todo_data = {"title": "测试待办事项", "description": "这是一个测试"}
    response = client.post("/api/todos/", json=todo_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "测试待办事项"
    assert data["description"] == "这是一个测试"
    assert data["completed"] is False
    return data["id"]


def test_get_todo():
    """测试获取待办事项"""
    # 先创建一个
    todo_id = test_create_todo()

    # 然后获取
    response = client.get(f"/api/todos/{todo_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == todo_id
    assert data["title"] == "测试待办事项"


def test_get_todos_list():
    """测试获取待办事项列表"""
    response = client.get("/api/todos/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    assert isinstance(data["items"], list)
    assert "total" in data["pagination"]


def test_invalid_todo():
    """测试无效的待办事项创建"""
    # 缺少必需的title字段
    invalid_data = {"description": "没有标题"}
    response = client.post("/api/todos/", json=invalid_data)
    assert response.status_code == 422


def test_get_nonexistent_todo():
    """测试获取不存在的待办事项"""
    response = client.get("/api/todos/99999")
    assert response.status_code == 404
