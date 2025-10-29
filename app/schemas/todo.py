"""
Pydantic schemas for Todo API request/response validation.

TODO: Implement Pydantic schemas for API validation
- Create Priority enum matching the database model
- Create TodoBase with common fields (title, description, priority, due_date)
- Create TodoCreate schema for POST requests:
  * Inherits from TodoBase
  * All fields optional except title
  * Add validation for title length (1-200 chars)
  * Add validation for description length (max 1000 chars)
- Create TodoUpdate schema for PATCH requests:
  * All fields optional for partial updates
  * Include completed field
  * Same validations as TodoCreate where applicable
- Create TodoResponse schema for API responses:
  * Inherits from TodoBase
  * Includes id, completed, created_at, updated_at
  * Configure Pydantic to work with SQLAlchemy models
- Create TodoListResponse for paginated list responses:
  * items: list of TodoResponse
  * total: total count
  * page info (limit, offset)
- Add custom validators for business rules (e.g., due_date in future)
"""
