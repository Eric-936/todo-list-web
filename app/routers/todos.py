from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlmodel import Session
from typing import Optional, Dict, Any, Generator
from datetime import datetime, date
import logging

# Dependencies
from app.database.database import engine
from app.services.cache_service import CacheService, cache_service
from app.services.todo_service import TodoService, TodoFilters

from app.schemas.todo import (
    TodoCreate,
    TodoUpdate,
    TodoResponse,
    TodoListResponse,
    PaginationMeta,
    TodoStatsResponse,
    HealthCheckResponse,
)
from app.models.todo import Priority

logger = logging.getLogger(__name__)


# Dependencies functions
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides database session."""
    with Session(engine) as session:
        yield session


def get_cache() -> CacheService:
    """FastAPI dependency that provides cache service."""
    return cache_service


# Router
router = APIRouter(
    prefix="/todos", tags=["todos"], responses={404: {"description": "Todo not found"}}
)


@router.get("/", response_model=TodoListResponse, summary="Get Todo List")
async def get_todos(
    # Filter parameters
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    priority: Optional[Priority] = Query(
        None, description="Filter by priority: LOW, MEDIUM, HIGH"
    ),
    search: Optional[str] = Query(
        None, description="Search keywords in title and description"
    ),
    due_date_from: Optional[date] = Query(
        None, description="Due date range - start date"
    ),
    due_date_to: Optional[date] = Query(None, description="Due date range - end date"),
    # Sort parameters
    sort_by: str = Query(
        "created_at",
        description="Sort field: created_at, updated_at, due_date, priority, title",
    ),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page, 1-100"),
    # Service dependencies
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Get Todo list with filtering, searching, sorting, and pagination."""
    try:
        offset = (page - 1) * page_size
        filters = TodoFilters(
            completed=completed,
            priority=priority,
            search=search,
            due_date_from=due_date_from,
            due_date_to=due_date_to,
            limit=page_size,
            offset=offset,
        )

        pagination_params = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        filter_params = {
            "completed": completed,
            "priority": priority.value if priority else None,
            "search": search,
            "due_date_from": due_date_from.isoformat() if due_date_from else None,
            "due_date_to": due_date_to.isoformat() if due_date_to else None,
        }

        # Try cache first
        cached_result = await cache.get_todos_list(filter_params, pagination_params)
        if cached_result:
            logger.debug("Cache hit for todos list query")
            return TodoListResponse(**cached_result)

        logger.debug("Cache miss for todos list query")

        # Query database
        result = TodoService.get_todos(db, filters)

        pagination_meta = PaginationMeta(
            page=result.current_page,
            page_size=result.limit,
            total=result.total,
            pages=result.total_pages,
            has_next=result.has_next,
            has_prev=result.has_prev,
        )

        todo_responses = [TodoResponse.from_orm(todo) for todo in result.items]

        response_data = TodoListResponse(
            items=todo_responses, pagination=pagination_meta
        )

        # Cache result
        cache_data = response_data.dict()
        await cache.cache_todos_list(filter_params, pagination_params, cache_data)

        return response_data

    except Exception as e:
        logger.error(f"Error in get_todos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve todos: {str(e)}",
        )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=TodoResponse,
    summary="Create Todo",
)
async def create_todo(
    todo_data: TodoCreate,
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Create a new Todo."""
    try:
        new_todo = TodoService.create_todo(db, todo_data.dict())

        # Cache new todo
        todo_dict = {
            "id": new_todo.id,
            "title": new_todo.title,
            "description": new_todo.description,
            "priority": new_todo.priority.value,
            "due_date": new_todo.due_date.isoformat() if new_todo.due_date else None,
            "completed": new_todo.completed,
            "created_at": new_todo.created_at.isoformat(),
            "updated_at": new_todo.updated_at.isoformat(),
        }
        await cache.cache_todo(new_todo.id, todo_dict)

        # Invalidate list caches
        await cache.invalidate_all_lists()
        await cache.delete("todos:stats")

        response = TodoResponse.from_orm(new_todo)
        logger.info(f"Created new todo: id={new_todo.id}, title='{new_todo.title}'")

        return response

    except Exception as e:
        logger.error(f"Error creating todo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create todo: {str(e)}",
        )


@router.get("/stats", response_model=TodoStatsResponse, summary="Get Todo Statistics")
async def get_todo_statistics(
    db: Session = Depends(get_db), cache: CacheService = Depends(get_cache)
):
    """Get Todo statistics for dashboard display."""
    try:
        # Check cache first
        cached_stats = await cache.get("todos:stats")
        if cached_stats:
            logger.debug("Cache hit for todo statistics")
            return TodoStatsResponse(**cached_stats)

        logger.debug("Cache miss for todo statistics")

        # Calculate statistics
        stats = TodoService.get_statistics(db)

        stats_response = TodoStatsResponse(
            total=stats["total"],
            completed=stats["completed"],
            pending=stats["pending"],
            overdue=stats["overdue"],
            by_priority=stats["by_priority"],
        )

        # Cache results with 60 second TTL
        cache_data = stats_response.dict()
        await cache.set("todos:stats", cache_data, ttl=60)

        logger.info(
            f"Generated todo statistics: total={stats['total']}, completed={stats['completed']}"
        )

        return stats_response

    except Exception as e:
        logger.error(f"Error generating todo statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate statistics: {str(e)}",
        )


@router.get("/health", response_model=HealthCheckResponse, summary="Health Check")
async def health_check(
    db: Session = Depends(get_db), cache: CacheService = Depends(get_cache)
):
    """System health check for monitoring."""
    import time
    from app.database.database import get_db_health

    try:
        check_timestamp = datetime.now()
        overall_status = "healthy"
        checks = {}

        # Database health check
        db_start_time = time.time()
        try:
            db_healthy = get_db_health()
            db_response_time = (time.time() - db_start_time) * 1000

            checks["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "response_time_ms": round(db_response_time, 2),
                "connected": db_healthy,
            }

            if not db_healthy:
                overall_status = "unhealthy"

        except Exception as e:
            checks["database"] = {
                "status": "unhealthy",
                "response_time_ms": 0,
                "connected": False,
                "error": str(e),
            }
            overall_status = "unhealthy"

        # Cache health check
        cache_start_time = time.time()
        try:
            cache_health = await cache.health_check()
            cache_response_time = (time.time() - cache_start_time) * 1000

            checks["cache"] = {
                "status": cache_health["status"],
                "response_time_ms": round(cache_response_time, 2),
                "connected": cache_health["connected"],
                "redis_info": cache_health.get("redis_info", {}),
                "cache_stats": cache_health.get("cache_stats", {}),
            }

            if cache_health["status"] != "healthy":
                if overall_status == "healthy":
                    overall_status = "degraded"

        except Exception as e:
            checks["cache"] = {
                "status": "unhealthy",
                "response_time_ms": 0,
                "connected": False,
                "error": str(e),
            }
            if overall_status == "healthy":
                overall_status = "degraded"

        # Application status
        checks["application"] = {
            "status": "healthy",
            "version": "1.0.0",
            "uptime_seconds": 3600,
            "timestamp": check_timestamp.isoformat(),
        }

        health_response = HealthCheckResponse(
            status=overall_status,
            timestamp=check_timestamp,
            version="1.0.0",
            checks=checks,
        )

        logger.info(f"Health check completed: status={overall_status}")

        if overall_status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_response.dict(),
            )

        return health_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get("/{todo_id}", response_model=TodoResponse, summary="Get Todo by ID")
async def get_todo(
    todo_id: int = Path(..., gt=0, description="Todo ID, must be greater than 0"),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Get a single Todo by ID."""
    try:
        # Try cache first
        cached_todo = await cache.get_todo(todo_id)
        if cached_todo:
            logger.debug(f"Cache hit for todo {todo_id}")
            return TodoResponse(**cached_todo)

        logger.debug(f"Cache miss for todo {todo_id}")

        # Query database
        todo = TodoService.get_todo_by_id(db, todo_id)

        # Cache result
        todo_dict = {
            "id": todo.id,
            "title": todo.title,
            "description": todo.description,
            "priority": todo.priority.value,
            "due_date": todo.due_date.isoformat() if todo.due_date else None,
            "completed": todo.completed,
            "created_at": todo.created_at.isoformat(),
            "updated_at": todo.updated_at.isoformat(),
        }
        await cache.cache_todo(todo_id, todo_dict)

        response = TodoResponse.from_orm(todo)
        logger.info(f"Retrieved todo from database: id={todo_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving todo {todo_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve todo: {str(e)}",
        )


@router.put("/{todo_id}", response_model=TodoResponse, summary="Update Todo")
async def update_todo(
    todo_id: int = Path(..., gt=0, description="Todo ID, must be greater than 0"),
    todo_update: TodoUpdate = Body(..., description="Todo update data"),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Update an existing Todo."""
    try:
        # Update todo
        updated_todo = TodoService.update_todo(
            db, todo_id, todo_update.dict(exclude_unset=True)
        )

        # Clear related caches
        await _clear_todo_caches(cache, todo_id)

        response = TodoResponse.from_orm(updated_todo)
        logger.info(f"Updated todo: id={todo_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating todo {todo_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update todo: {str(e)}",
        )


@router.delete(
    "/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Todo"
)
async def delete_todo(
    todo_id: int = Path(..., gt=0, description="Todo ID, must be greater than 0"),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Delete a Todo by ID."""
    try:
        # Verify todo exists and delete
        _validate_todo_exists(db, todo_id)

        TodoService.delete_todo(db, todo_id)

        # Clear related caches
        await _clear_todo_caches(cache, todo_id)

        logger.info(f"Deleted todo: id={todo_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting todo {todo_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete todo: {str(e)}",
        )


@router.post(
    "/{todo_id}/complete", response_model=TodoResponse, summary="Mark Todo as Complete"
)
async def mark_todo_complete(
    todo_id: int = Path(..., gt=0, description="Todo ID, must be greater than 0"),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Mark a Todo as complete."""
    try:
        # Update completion status
        updated_todo = TodoService.mark_completed(db, todo_id)

        # Clear related caches
        await _clear_todo_caches(cache, todo_id)

        response = TodoResponse.from_orm(updated_todo)
        logger.info(f"Marked todo complete: id={todo_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking todo complete {todo_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark todo complete: {str(e)}",
        )


@router.post(
    "/{todo_id}/incomplete",
    response_model=TodoResponse,
    summary="Mark Todo as Incomplete",
)
async def mark_todo_incomplete(
    todo_id: int = Path(..., gt=0, description="Todo ID, must be greater than 0"),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Mark a Todo as incomplete."""
    try:
        # Update completion status
        updated_todo = TodoService.mark_incomplete(db, todo_id)

        # Clear related caches
        await _clear_todo_caches(cache, todo_id)

        response = TodoResponse.from_orm(updated_todo)
        logger.info(f"Marked todo incomplete: id={todo_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking todo incomplete {todo_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark todo incomplete: {str(e)}",
        )


# Utility functions
def _validate_todo_exists(db: Session, todo_id: int) -> None:
    """Validate that a Todo exists, raising 404 if not found."""
    try:
        TodoService.get_todo_by_id(db, todo_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Todo with id {todo_id} not found",
            )
        raise


async def _clear_todo_caches(cache: CacheService, todo_id: int) -> None:
    """Clear all caches related to a Todo."""
    try:
        await cache.delete(f"todo:{todo_id}")
        await cache.delete_pattern("todos:list:*")
        await cache.delete("todos:stats")

        logger.debug(f"Cleared caches for todo {todo_id}")

    except Exception as e:
        logger.error(f"Failed to clear caches for todo {todo_id}: {str(e)}")


def _build_cache_key(filters: Dict[str, Any], pagination: Dict[str, int]) -> str:
    """Build a consistent cache key for query parameters."""
    import hashlib
    import json

    try:
        # Filter None values
        normalized_filters = {k: v for k, v in filters.items() if v is not None}

        # Sort parameters for consistency
        sorted_filters = dict(sorted(normalized_filters.items()))
        sorted_pagination = dict(sorted(pagination.items()))

        params = {"filters": sorted_filters, "pagination": sorted_pagination}

        params_str = json.dumps(params, sort_keys=True, default=str)
        hash_value = hashlib.md5(params_str.encode()).hexdigest()[:12]

        return f"todos:list:{hash_value}"

    except Exception as e:
        logger.error(f"Failed to build cache key: {str(e)}")
        import time

        return f"todos:list:fallback_{int(time.time())}"
