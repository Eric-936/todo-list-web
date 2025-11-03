"""
Todo List API Routers
"""

import logging
from typing import Generator, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from app.config import settings
from app.database.database import engine
from app.models.todo import Priority
from app.services.cache_service import CacheService, cache_service
from app.services.todo_service import TodoFilters, TodoService
from app.schemas.todo import (
    PaginationMeta,
    TodoCreate,
    TodoListResponse,
    TodoResponse,
    TodoStatsResponse,
    TodoUpdate,
)


# Set up logger
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
    prefix="/todos",
    tags=["todos"],
    responses={404: {"description": "Todo not found"}},
)


# Get Todo list with filtering, searching, sorting, and pagination.
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
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Items per page, 1-{settings.max_page_size}",
    ),
    # Service dependencies
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Get Todo list with filtering, searching, and pagination."""
    try:
        offset = (page - 1) * page_size
        filters = TodoFilters(
            completed=completed,
            priority=priority,
            search=search,
            limit=page_size,
            offset=offset,
        )

        pagination_params = {
            "page": page,
            "page_size": page_size,
        }

        filter_params = {
            "completed": completed,
            "priority": priority.value if priority else None,
            "search": search,
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
        cache_data = response_data.model_dump()
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
        new_todo = TodoService.create_todo(db, todo_data.model_dump())

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
        )

        # Cache results with 60 second TTL
        cache_data = stats_response.model_dump()
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


@router.patch("/{todo_id}", response_model=TodoResponse, summary="Update Todo")
async def update_todo(
    todo_id: int = Path(..., gt=0, description="Todo ID, must be greater than 0"),
    todo_update: TodoUpdate = Body(..., description="Todo update data"),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
):
    """Partially update an existing Todo."""
    try:
        # Update todo
        updated_todo = TodoService.update_todo(
            db, todo_id, todo_update.model_dump(exclude_unset=True)
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
