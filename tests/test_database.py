"""
Database tests - Step by step implementation.
"""

import pytest
import os
from app.database.database import engine, get_db_health
from app.config import settings

# Fundation tests for database configuration

def test_database_engine_exists():
    """Test that database engine is created."""
    assert engine is not None

def test_database_url_from_config():
    """Test that database URL comes from config."""
    assert settings.database_url is not None
    assert settings.database_url.startswith("sqlite:///")

def test_engine_url_matches_config():
    """Test that engine URL matches config URL."""
    engine_url = str(engine.url)
    config_url = settings.database_url
    assert engine_url == config_url


# Database connection tests

def test_database_health_check():
    """Test database health check function."""
    health = get_db_health()
    
    assert health is True


# Database file tests

def test_sqlite_file_creation():
    """Test that SQLite database file is created."""
    # Parse the database path from URL
    db_path = settings.database_url.replace("sqlite:///", "")
    
    # File should exist after we've used the database
    health = get_db_health()  # This should create the file
    assert health is True
    
    # Check if file exists
    if not db_path.startswith(":memory:"):
        assert os.path.exists(db_path)