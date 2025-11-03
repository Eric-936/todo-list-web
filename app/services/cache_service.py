import hashlib
import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as redis

from app.config import settings


logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis caching service for Todo API operations.

    Provides methods for caching individual todos, todo lists, and managing
    cache invalidation. Uses consistent key naming and handles Redis connection
    errors gracefully.
    """

    def __init__(self):
        """
        Initialize CacheService with Redis connection.

        Creates Redis client using configuration settings and sets up
        connection parameters with proper error handling.
        """
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = settings.cache_ttl
        self.is_connected = False

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get or create Redis client with connection handling."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    settings.redis_connection_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                await self.redis_client.ping()
                self.is_connected = True
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None
                self.is_connected = False

        return self.redis_client

    async def _execute_with_fallback(self, operation, *args, **kwargs):
        """Execute Redis operation with error handling and fallback."""
        try:
            client = await self._get_redis_client()
            if client is None:
                return None
            return await operation(client, *args, **kwargs)
        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            self.is_connected = False
            self.redis_client = None
            return None

    # ================== Core Cache Operations ==================

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve cached value by key.

        Args:
            key (str): Cache key to retrieve

        Returns:
            Optional[Any]: Cached value if exists and valid, None otherwise

        Example:
            cached_data = await cache_service.get("todo:123")
        """

        async def _get_operation(client, key):
            value = await client.get(key)
            if value is None:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to deserialize cached value for key {key}: {e}")
                await client.delete(key)  # Remove corrupted data
                return None

        result = await self._execute_with_fallback(_get_operation, key)
        if result is not None:
            logger.debug(f"Cache hit for key: {key}")
        else:
            logger.debug(f"Cache miss for key: {key}")
        return result

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store value in cache with optional expiration.

        Args:
            key (str): Cache key to store under
            value (Any): Value to cache (will be JSON serialized)
            ttl (Optional[int]): Time to live in seconds, uses default if None

        Returns:
            bool: True if successful, False otherwise

        Example:
            success = await cache_service.set("todo:123", todo_data, ttl=3600)
        """

        async def _set_operation(client, key, value, ttl):
            try:
                serialized_value = json.dumps(value, default=str)
                if ttl:
                    result = await client.setex(key, ttl, serialized_value)
                else:
                    result = await client.setex(key, self.default_ttl, serialized_value)
                return bool(result)
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to serialize value for key {key}: {e}")
                return False

        effective_ttl = ttl if ttl is not None else self.default_ttl
        result = await self._execute_with_fallback(
            _set_operation, key, value, effective_ttl
        )
        if result:
            logger.debug(f"Cached key: {key} (TTL: {effective_ttl}s)")
        return bool(result)

    async def delete(self, key: str) -> bool:
        """
        Remove specific key from cache.

        Args:
            key (str): Cache key to delete

        Returns:
            bool: True if key was deleted, False if key didn't exist

        Example:
            deleted = await cache_service.delete("todo:123")
        """

        async def _delete_operation(client, key):
            result = await client.delete(key)
            return result > 0

        result = await self._execute_with_fallback(_delete_operation, key)
        if result:
            logger.debug(f"Deleted cache key: {key}")
        return bool(result)

    async def delete_pattern(self, pattern: str) -> int:
        """
        Remove all keys matching pattern.

        Args:
            pattern (str): Redis pattern to match keys (e.g., "todos:list:*")

        Returns:
            int: Number of keys deleted

        Example:
            count = await cache_service.delete_pattern("todos:list:*")
        """

        async def _delete_pattern_operation(client, pattern):
            keys = []
            try:
                # Use scan_iter to find matching keys
                async for key in client.scan_iter(match=pattern, count=100):
                    keys.append(key)

                # Delete keys in batches if any found
                if keys:
                    # Redis delete can handle multiple keys at once
                    deleted_count = await client.delete(*keys)
                    return deleted_count
                else:
                    return 0
            except Exception as e:
                logger.error(f"Error during pattern scan or delete: {e}")
                return 0

        result = await self._execute_with_fallback(_delete_pattern_operation, pattern)
        count = result or 0
        if count > 0:
            logger.debug(f"Deleted {count} keys matching pattern: {pattern}")
        return count

    # ================== Todo-Specific Cache Methods ==================

    async def get_todo(self, todo_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached todo by ID.

        Args:
            todo_id (int): ID of the todo to retrieve

        Returns:
            Optional[Dict[str, Any]]: Todo data if cached, None otherwise

        Example:
            todo = await cache_service.get_todo(123)
            if todo:
                print(f"Cache hit for todo {todo_id}")
        """
        key = self._generate_todo_key(todo_id)
        return await self.get(key)

    async def cache_todo(
        self, todo_id: int, todo_data: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """
        Cache single todo data.

        Args:
            todo_id (int): ID of the todo to cache
            todo_data (Dict[str, Any]): Todo data to cache
            ttl (Optional[int]): Custom TTL, uses default if None

        Returns:
            bool: True if cached successfully, False otherwise

        Example:
            cached = await cache_service.cache_todo(123, {"title": "Test", ...})
        """
        key = self._generate_todo_key(todo_id)
        return await self.set(key, todo_data, ttl)

    async def get_todos_list(
        self, filters: Dict[str, Any], pagination: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached todo list based on filters and pagination.

        Args:
            filters (Dict[str, Any]): Filter parameters applied to the query
            pagination (Dict[str, Any]): Pagination parameters (page, page_size)

        Returns:
            Optional[Dict[str, Any]]: Cached list result with items and metadata, None if not cached

        Example:
            filters = {"completed": False, "priority": "high"}
            pagination = {"page": 1, "page_size": 10}
            result = await cache_service.get_todos_list(filters, pagination)
        """
        key = self._generate_list_key(filters, pagination)
        return await self.get(key)

    async def cache_todos_list(
        self,
        filters: Dict[str, Any],
        pagination: Dict[str, Any],
        list_data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache todo list with filters and pagination.

        Args:
            filters (Dict[str, Any]): Filter parameters used in the query
            pagination (Dict[str, Any]): Pagination parameters used
            list_data (Dict[str, Any]): List result to cache (items + metadata)
            ttl (Optional[int]): Custom TTL, uses default if None

        Returns:
            bool: True if cached successfully, False otherwise

        Example:
            filters = {"completed": False}
            pagination = {"page": 1, "page_size": 10}
            result = {"items": [...], "total": 25, "page": 1, "pages": 3}
            cached = await cache_service.cache_todos_list(filters, pagination, result)
        """
        key = self._generate_list_key(filters, pagination)
        return await self.set(key, list_data, ttl)

    # ================== Cache Invalidation Methods ==================

    async def invalidate_todo(self, todo_id: int) -> bool:
        """
        Invalidate cache for specific todo.

        Args:
            todo_id (int): ID of todo to invalidate

        Returns:
            bool: True if invalidated, False if not found

        Example:
            # After updating todo 123
            await cache_service.invalidate_todo(123)
        """
        key = self._generate_todo_key(todo_id)
        result = await self.delete(key)

        # Also invalidate all list caches since the todo data changed
        await self.invalidate_all_lists()

        return result

    async def invalidate_all_lists(self) -> int:
        """
        Invalidate all cached todo lists.

        Called when any todo data changes to ensure list consistency.

        Returns:
            int: Number of list caches invalidated

        Example:
            # After creating, updating, or deleting any todo
            count = await cache_service.invalidate_all_lists()
            logger.info(f"Invalidated {count} list caches")
        """
        pattern = "todos:list:*"
        count = await self.delete_pattern(pattern)
        if count > 0:
            logger.info(f"Invalidated {count} todo list caches")
        return count

    async def invalidate_all(self) -> int:
        """
        Clear all todo-related caches.

        Nuclear option for cache invalidation, removes all todos and lists.

        Returns:
            int: Total number of keys invalidated

        Example:
            # During maintenance or major data changes
            count = await cache_service.invalidate_all()
        """
        patterns = ["todo:*", "todos:list:*"]
        total_count = 0

        for pattern in patterns:
            count = await self.delete_pattern(pattern)
            total_count += count

        if total_count > 0:
            logger.info(f"Invalidated all todo caches: {total_count} keys")
        return total_count

    # ================== Utility and Health Check Methods ==================

    def _generate_list_key(
        self, filters: Dict[str, Any], pagination: Dict[str, Any]
    ) -> str:
        """
        Generate consistent cache key for todo lists.

        Args:
            filters (Dict[str, Any]): Filter parameters
            pagination (Dict[str, Any]): Pagination parameters

        Returns:
            str: Generated cache key

        Example:
            key = cache_service._generate_list_key(
                {"completed": False, "priority": "high"},
                {"page": 1, "page_size": 10}
            )
            # Returns: "todos:list:a1b2c3d4e5f6..."
        """
        # Create a normalized representation of the parameters
        # Sort keys to ensure consistent ordering
        normalized_filters = {k: v for k, v in sorted(filters.items()) if v is not None}
        normalized_pagination = {
            k: v for k, v in sorted(pagination.items()) if v is not None
        }

        # Combine parameters into a single dictionary
        params = {"filters": normalized_filters, "pagination": normalized_pagination}

        # Create a hash of the parameters
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[
            :12
        ]  # Use first 12 chars

        return f"todos:list:{params_hash}"

    def _generate_todo_key(self, todo_id: int) -> str:
        """
        Generate cache key for individual todo.

        Args:
            todo_id (int): Todo ID

        Returns:
            str: Generated cache key

        Example:
            key = cache_service._generate_todo_key(123)
            # Returns: "todo:123"
        """
        return f"todo:{todo_id}"

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Redis connection and cache health.

        Returns:
            Dict[str, Any]: Health status with connection info and basic stats

        Example:
            health = await cache_service.health_check()
            # Returns: {
            #     "status": "healthy",
            #     "connected": True,
            #     "redis_info": {...},
            #     "cache_stats": {...}
            # }
        """
        health_status = {
            "status": "unhealthy",
            "connected": False,
            "redis_info": {},
            "cache_stats": {},
            "error": None,
        }

        try:
            client = await self._get_redis_client()
            if client is None:
                health_status["error"] = "Failed to establish Redis connection"
                return health_status

            # Test ping
            pong = await client.ping()
            if pong:
                health_status["connected"] = True
                health_status["status"] = "healthy"

                # Get Redis info
                info = await client.info()
                health_status["redis_info"] = {
                    "redis_version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "total_commands_processed": info.get("total_commands_processed"),
                }

                # Get cache stats
                health_status["cache_stats"] = await self.get_cache_stats()

        except Exception as e:
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        return health_status

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache usage statistics.

        Returns:
            Dict[str, Any]: Statistics about cache usage and performance

        Example:
            stats = await cache_service.get_cache_stats()
            # Returns: {
            #     "total_keys": 150,
            #     "todo_keys": 100,
            #     "list_keys": 50,
            #     "memory_usage": "2.5MB"
            # }
        """
        stats = {"total_keys": 0, "todo_keys": 0, "list_keys": 0, "memory_usage": "0B"}

        try:
            client = await self._get_redis_client()
            if client is None:
                return stats

            # Count total keys
            total_keys = await client.dbsize()
            stats["total_keys"] = total_keys

            # Count todo-specific keys
            todo_keys = []
            list_keys = []

            try:
                # Count todo keys
                async for key in client.scan_iter(match="todo:*", count=100):
                    todo_keys.append(key)

                # Count list keys
                async for key in client.scan_iter(match="todos:list:*", count=100):
                    list_keys.append(key)

            except Exception as scan_error:
                logger.error(f"Error during key scanning: {scan_error}")
                # Continue with partial stats

            stats["todo_keys"] = len(todo_keys)
            stats["list_keys"] = len(list_keys)

            # Get memory usage
            try:
                info = await client.info("memory")
                stats["memory_usage"] = info.get("used_memory_human", "0B")
            except Exception as memory_error:
                logger.error(f"Error getting memory info: {memory_error}")
                stats["memory_usage"] = "Unknown"

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")

        return stats


# Global cache service instance
cache_service = CacheService()
