"""
SQLAlchemy database model for Todo items.

TODO: Implement Todo database model
- Create Todo class inheriting from SQLAlchemy Base
- Define table name and columns:
  * id: Integer primary key, auto-increment
  * title: String(200), required, not null
  * description: Text, optional, max 1000 chars
  * priority: Enum (LOW, MEDIUM, HIGH), default MEDIUM
  * due_date: Date, optional
  * completed: Boolean, default False
  * created_at: DateTime with timezone, auto-generated
  * updated_at: DateTime with timezone, auto-updated
- Create Priority enum class for priority levels
- Add table constraints and indexes for performance
- Add __repr__ method for debugging
- Optional: Add validation methods for business rules
"""
