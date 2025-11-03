"""
Business logic service for Todo operations.
"""

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlmodel import Session, func, or_, select

from app.config import settings
from app.models.todo import Priority, Todo


class TodoFilters:
    """Data class for organizing filter parameters"""

    def __init__(
        self,
        completed: Optional[bool] = None,
        priority: Optional[Priority] = None,
        search: Optional[str] = None,
        limit: int = settings.default_page_size,
        offset: int = 0,
    ):
        self.completed = completed
        self.priority = priority
        self.search = search
        self.limit = max(
            1, min(limit, settings.max_page_size)
        )  # Limit between 1-max_page_size
        self.offset = max(0, offset)


class PaginationResult:
    """Pagination result data class"""

    def __init__(self, items: List[Todo], total: int, limit: int, offset: int):
        self.items = items
        self.total = total
        self.limit = limit
        self.offset = offset
        self.has_next = offset + limit < total
        self.has_prev = offset > 0
        self.total_pages = (total + limit - 1) // limit
        self.current_page = (offset // limit) + 1


class TodoService:
    """Todo business logic service class"""

    @staticmethod
    def create_todo(db: Session, todo_data: Dict[str, Any]) -> Todo:
        """
        Create a new todo

        Args:
            db: Database session
            todo_data: Todo data dictionary

        Returns:
            Todo: Created todo object

        Raises:
            HTTPException: Raised when creation fails
        """
        try:
            # Create todo object
            todo = Todo(**todo_data)

            # Save to database
            db.add(todo)
            db.commit()
            db.refresh(todo)

            return todo

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create todo: {str(e)}",
            )

    @staticmethod
    def get_todo_by_id(db: Session, todo_id: int) -> Todo:
        """
        Get a single todo by ID

        Args:
            db: Database session
            todo_id: Todo ID

        Returns:
            Todo: Todo object

        Raises:
            HTTPException: Raised with 404 when todo not found
        """
        todo = db.get(Todo, todo_id)
        if not todo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Todo with id {todo_id} not found",
            )
        return todo

    @staticmethod
    def get_todos(db: Session, filters: TodoFilters) -> PaginationResult:
        """
        Get filtered and paginated todo list

        Args:
            db: Database session
            filters: Filter and pagination parameters

        Returns:
            PaginationResult: Pagination result object
        """
        # Build base query
        query = select(Todo)
        count_query = select(func.count(Todo.id))

        # Apply filter conditions
        where_conditions = TodoService._build_where_conditions(filters)

        if where_conditions:
            # Combine all conditions with AND
            combined_condition = where_conditions[0]
            for condition in where_conditions[1:]:
                combined_condition = combined_condition & condition

            query = query.where(combined_condition)
            count_query = count_query.where(combined_condition)

        # Get total count
        total = db.exec(count_query).one()

        # Apply default sorting (newest first) and pagination
        query = query.order_by(Todo.created_at.desc())
        query = query.offset(filters.offset).limit(filters.limit)

        # Execute query
        todos = db.exec(query).all()

        return PaginationResult(
            items=list(todos), total=total, limit=filters.limit, offset=filters.offset
        )

    @staticmethod
    def _build_where_conditions(filters: TodoFilters) -> List:
        """Build WHERE condition list"""
        conditions = []

        # Filter by completion status
        if filters.completed is not None:
            conditions.append(Todo.completed == filters.completed)

        # Filter by priority
        if filters.priority is not None:
            conditions.append(Todo.priority == filters.priority)

        # Filter by search keywords
        if filters.search:
            search_term = f"%{filters.search.lower()}%"
            search_condition = or_(
                func.lower(Todo.title).like(search_term),
                func.lower(Todo.description).like(search_term),
            )
            conditions.append(search_condition)

        return conditions

    @staticmethod
    def update_todo(db: Session, todo_id: int, update_data: Dict[str, Any]) -> Todo:
        """
        Update a todo

        Args:
            db: Database session
            todo_id: Todo ID
            update_data: Update data dictionary

        Returns:
            Todo: Updated todo object

        Raises:
            HTTPException: Raised when todo not found or update fails
        """
        # Get existing todo
        todo = TodoService.get_todo_by_id(db, todo_id)

        try:
            # Update fields
            for field, value in update_data.items():
                if hasattr(todo, field):
                    setattr(todo, field, value)

            # Update timestamp
            todo.update_timestamp()

            # Save changes
            db.add(todo)
            db.commit()
            db.refresh(todo)

            return todo

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update todo: {str(e)}",
            )

    @staticmethod
    def delete_todo(db: Session, todo_id: int) -> Dict[str, str]:
        """
        Delete a todo

        Args:
            db: Database session
            todo_id: Todo ID

        Returns:
            Dict: Success message

        Raises:
            HTTPException: Raised with 404 when todo not found
        """
        # Get existing todo (will raise 404 if not found)
        todo = TodoService.get_todo_by_id(db, todo_id)

        try:
            # Delete todo
            db.delete(todo)
            db.commit()

            return {"message": f"Todo {todo_id} deleted successfully"}

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete todo: {str(e)}",
            )

    @staticmethod
    def get_statistics(db: Session) -> Dict[str, Any]:
        """
        Get todo statistics

        Args:
            db: Database session

        Returns:
            Dict: Statistics information
        """
        # Total count
        total = db.exec(select(func.count(Todo.id))).one()

        # Completed count
        completed = db.exec(select(func.count(Todo.id)).where(Todo.completed)).one()

        # Pending count
        pending = total - completed

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
        }
