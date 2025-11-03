"""
Unit tests for CacheService module.

Tests the caching functionality with mocked Redis connections to verify
business logic without requiring actual Redis server.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.cache_service import CacheService


class TestCacheService:
    """Test cases for CacheService class."""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing."""
        return CacheService()

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client for testing."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        return mock_client


class TestCoreOperations:
    """Test core cache operations (get, set, delete, delete_pattern)."""

    @pytest.fixture
    def cache_service(self):
        return CacheService()

    @pytest.fixture
    def mock_redis_client(self):
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        return mock_client

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache_service, mock_redis_client):
        """Test retrieving non-existent key returns None."""
        # Arrange
        mock_redis_client.get.return_value = None

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.get("nonexistent:key")

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, cache_service, mock_redis_client):
        """Test setting value with custom TTL."""
        # Arrange
        test_data = {"id": 789}
        custom_ttl = 3600
        mock_redis_client.setex.return_value = True

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.set("test:key", test_data, ttl=custom_ttl)

            # Assert
            assert result is True
            mock_redis_client.setex.assert_called_once_with(
                "test:key", custom_ttl, json.dumps(test_data, default=str)
            )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, cache_service, mock_redis_client):
        """Test deleting non-existent key."""
        # Arrange
        mock_redis_client.delete.return_value = 0

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.delete("nonexistent:key")

            # Assert
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_pattern_with_matches(self, cache_service, mock_redis_client):
        """Test deleting keys by pattern with matches."""
        # Arrange
        matching_keys = ["todos:list:abc123", "todos:list:def456"]

        # Create a proper async iterator mock
        async def mock_scan_iter(**kwargs):
            for key in matching_keys:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.return_value = len(matching_keys)

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.delete_pattern("todos:list:*")

            # Assert
            assert result == 2
            mock_redis_client.delete.assert_called_once_with(*matching_keys)


class TestTodoSpecificMethods:
    """Test todo-specific cache methods."""

    @pytest.fixture
    def cache_service(self):
        return CacheService()

    @pytest.fixture
    def mock_redis_client(self):
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        return mock_client

    @pytest.fixture
    def sample_todo(self):
        return {
            "id": 123,
            "title": "Test Todo",
            "description": "Test description",
            "completed": False,
            "priority": "medium",
        }

    @pytest.mark.asyncio
    async def test_get_todo(self, cache_service, mock_redis_client, sample_todo):
        """Test getting cached todo by ID."""
        # Arrange
        mock_redis_client.get.return_value = json.dumps(sample_todo)

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.get_todo(123)

            # Assert
            assert result == sample_todo
            mock_redis_client.get.assert_called_once_with("todo:123")

    @pytest.mark.asyncio
    async def test_cache_todo(self, cache_service, mock_redis_client, sample_todo):
        """Test caching a todo."""
        # Arrange
        mock_redis_client.setex.return_value = True

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.cache_todo(123, sample_todo)

            # Assert
            assert result is True
            mock_redis_client.setex.assert_called_once_with(
                "todo:123",
                cache_service.default_ttl,
                json.dumps(sample_todo, default=str),
            )

    @pytest.mark.asyncio
    async def test_get_todos_list(self, cache_service, mock_redis_client):
        """Test getting cached todo list."""
        # Arrange
        filters = {"completed": False, "priority": "high"}
        pagination = {"page": 1, "page_size": 10}
        list_data = {"items": [], "total": 0, "page": 1}

        expected_key = cache_service._generate_list_key(filters, pagination)
        mock_redis_client.get.return_value = json.dumps(list_data)

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.get_todos_list(filters, pagination)

            # Assert
            assert result == list_data
            mock_redis_client.get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_cache_todos_list(self, cache_service, mock_redis_client):
        """Test caching a todo list."""
        # Arrange
        filters = {"completed": True}
        pagination = {"page": 2, "page_size": 20}
        list_data = {"items": [], "total": 0, "page": 2}

        expected_key = cache_service._generate_list_key(filters, pagination)
        mock_redis_client.setex.return_value = True

        with patch.object(
            cache_service, "_get_redis_client", return_value=mock_redis_client
        ):
            # Act
            result = await cache_service.cache_todos_list(
                filters, pagination, list_data
            )

            # Assert
            assert result is True
            mock_redis_client.setex.assert_called_once_with(
                expected_key,
                cache_service.default_ttl,
                json.dumps(list_data, default=str),
            )


class TestCacheInvalidation:
    """Test cache invalidation methods."""

    @pytest.fixture
    def cache_service(self):
        return CacheService()

    @pytest.fixture
    def mock_redis_client(self):
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        return mock_client

    @pytest.mark.asyncio
    async def test_invalidate_todo(self, cache_service, mock_redis_client):
        """Test invalidating specific todo cache."""
        # Arrange
        mock_redis_client.delete.return_value = 1

        # Create async iterator for empty list
        async def empty_async_iter():
            return
            yield  # This will never execute but makes it a generator

        mock_redis_client.scan_iter.return_value = empty_async_iter()

        with patch.object(cache_service, '_get_redis_client', return_value=mock_redis_client):
            # Act
            result = await cache_service.invalidate_todo(123)

            # Assert
            assert result is True
            # Should delete the specific todo
            assert mock_redis_client.delete.call_count >= 1
            # Should also call invalidate_all_lists (which scans for list patterns)
            mock_redis_client.scan_iter.assert_called_with(match="todos:list:*", count=100)

    @pytest.mark.asyncio
    async def test_invalidate_all_lists(self, cache_service, mock_redis_client):
        """Test invalidating all list caches."""
        # Arrange
        list_keys = ["todos:list:abc", "todos:list:def"]

        # Create async iterator function that can be called
        async def async_list_keys(**kwargs):
            for key in list_keys:
                yield key

        mock_redis_client.scan_iter = async_list_keys
        mock_redis_client.delete.return_value = len(list_keys)

        with patch.object(cache_service, '_get_redis_client', return_value=mock_redis_client):
            # Act
            result = await cache_service.invalidate_all_lists()

            # Assert
            assert result == 2
            mock_redis_client.delete.assert_called_once_with(*list_keys)

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache_service, mock_redis_client):
        """Test invalidating all todo-related caches."""
        # Arrange
        todo_keys = ["todo:1", "todo:2"]
        list_keys = ["todos:list:abc"]

        # Mock scan_iter to return different results for different patterns
        def mock_scan_iter(match=None, **kwargs):
            if match == "todo:*":
                async def todo_keys_iter():
                    for key in todo_keys:
                        yield key
                return todo_keys_iter()
            elif match == "todos:list:*":
                async def list_keys_iter():
                    for key in list_keys:
                        yield key
                return list_keys_iter()
            else:
                async def empty_iter():
                    return
                    yield
                return empty_iter()

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.side_effect = [len(todo_keys), len(list_keys)]

        with patch.object(cache_service, '_get_redis_client', return_value=mock_redis_client):
            # Act
            result = await cache_service.invalidate_all()

            # Assert
            assert result == 3  # 2 todo keys + 1 list key
            assert mock_redis_client.delete.call_count == 2


class TestKeyGeneration:
    """Test cache key generation methods."""

    @pytest.fixture
    def cache_service(self):
        return CacheService()

    def test_generate_todo_key(self, cache_service):
        """Test todo key generation."""
        # Act
        key = cache_service._generate_todo_key(123)

        # Assert
        assert key == "todo:123"

    def test_generate_list_key_consistency(self, cache_service):
        """Test that same parameters generate same key regardless of order."""
        # Arrange
        filters1 = {"completed": False, "priority": "high"}
        filters2 = {"priority": "high", "completed": False}  # Different order
        pagination = {"page": 1, "page_size": 10}

        # Act
        key1 = cache_service._generate_list_key(filters1, pagination)
        key2 = cache_service._generate_list_key(filters2, pagination)

        # Assert
        assert key1 == key2
        assert key1.startswith("todos:list:")

    def test_generate_list_key_different_params(self, cache_service):
        """Test that different parameters generate different keys."""
        # Arrange
        filters1 = {"completed": False}
        filters2 = {"completed": True}
        pagination = {"page": 1, "page_size": 10}

        # Act
        key1 = cache_service._generate_list_key(filters1, pagination)
        key2 = cache_service._generate_list_key(filters2, pagination)

        # Assert
        assert key1 != key2
        assert key1.startswith("todos:list:")
        assert key2.startswith("todos:list:")


class TestErrorHandling:
    """Test error handling and fallback behavior."""

    @pytest.fixture
    def cache_service(self):
        return CacheService()

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, cache_service):
        """Test graceful handling of Redis connection failure."""
        # Arrange
        with patch.object(cache_service, "_get_redis_client", return_value=None):
            # Act
            result = await cache_service.get("test:key")

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_health_check_connection_failure(self, cache_service):
        """Test health check with connection failure."""
        # Arrange
        with patch.object(cache_service, "_get_redis_client", return_value=None):
            # Act
            health = await cache_service.health_check()

            # Assert
            assert health["status"] == "unhealthy"
            assert health["connected"] is False
            assert "error" in health

    @pytest.mark.asyncio
    async def test_health_check_success(self, cache_service):
        """Test successful health check."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            "redis_version": "7.0.0",
            "connected_clients": 1,
            "used_memory_human": "1.5M",
        }
        mock_client.dbsize.return_value = 10

        # Create async iterators for scan operations
        async def empty_iter():
            return
            yield

        mock_client.scan_iter.return_value = empty_iter()

        with patch.object(cache_service, "_get_redis_client", return_value=mock_client):
            # Act
            health = await cache_service.health_check()

            # Assert
            assert health["status"] == "healthy"
            assert health["connected"] is True
            assert "redis_info" in health
            assert "cache_stats" in health
