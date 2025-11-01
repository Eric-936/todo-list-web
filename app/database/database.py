"""
Database configuration and session management using SQLModel.
"""

from typing import Generator
from sqlmodel import SQLModel, create_engine, Session, text
from app.config import settings


# Create SQLite engine with proper configuration
engine = create_engine(
    settings.database_url,
    echo=settings.log_level.upper() == "DEBUG",  # Echo SQL queries in debug mode
    connect_args={"check_same_thread": False}    # Required for SQLite
)


def create_db_and_tables():
    """Create database tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides database session.
    
    Yields:
        Session: SQLModel database session
    """
    with Session(engine) as session:
        yield session


def get_db_health() -> bool:
    """
    Check database health/connectivity.
    
    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        with Session(engine) as session:
            # Simple query to test connection - use text() for raw SQL
            session.exec(text("SELECT 1")).one()
            return True
    except Exception:
        return False


def init_db():
    """
    Initialize database on application startup.
    Creates tables and optionally adds sample data.
    """
    create_db_and_tables()
    
    # Optional: Add sample data for development
    if settings.log_level.upper() == "DEBUG":
        _create_sample_data()


def _create_sample_data():
    """Create sample data for development (optional)."""
    # Will implement this after creating Todo model
    pass