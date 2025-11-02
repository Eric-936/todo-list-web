"""
Tests for configuration settings.
"""

import os
import pytest
from unittest.mock import patch
from app.config import Settings


def test_environment_variable_override():
    """Test that environment variables override default values."""
    env_vars = {
        "LOG_LEVEL": "DEBUG",
        "DATABASE_URL": "sqlite:///./test.db",
        "REDIS_HOST": "redis.example.com",
        "REDIS_PORT": "6380",
        "REDIS_PASSWORD": "secret123",
        "REDIS_DB": "1",
        "CACHE_TTL": "60",
    }

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        assert settings.log_level == "DEBUG"
        assert settings.database_url == "sqlite:///./test.db"
        assert settings.redis_host == "redis.example.com"
        assert settings.redis_port == 6380
        assert settings.redis_password == "secret123"
        assert settings.redis_db == 1
        assert settings.cache_ttl == 60


def test_redis_connection_url_without_password():
    """Test Redis connection URL generation without password."""
    settings = Settings()

    expected_url = "redis://localhost:6379/0"
    assert settings.redis_connection_url == expected_url


def test_redis_connection_url_with_password():
    """Test Redis connection URL generation with password."""
    env_vars = {
        "REDIS_PASSWORD": "mypassword",
        "REDIS_HOST": "redis.example.com",
        "REDIS_PORT": "6379",
        "REDIS_DB": "2",
    }

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        expected_url = "redis://:mypassword@redis.example.com:6379/2"
        assert settings.redis_connection_url == expected_url


def test_redis_connection_url_with_full_url():
    """Test Redis connection URL when full URL is provided."""
    env_vars = {"REDIS_URL": "redis://user:pass@custom.redis.com:6379/5"}

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        # Should use the full URL directly
        assert (
            settings.redis_connection_url == "redis://user:pass@custom.redis.com:6379/5"
        )


def test_case_insensitive_env_vars():
    """Test that environment variables are case insensitive."""
    env_vars = {
        "log_level": "ERROR",  # lowercase
        "CACHE_TTL": "120",  # uppercase
        "Redis_Host": "example.com",  # mixed case
    }

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        assert settings.log_level == "ERROR"
        assert settings.cache_ttl == 120
        assert settings.redis_host == "example.com"


def test_type_validation():
    """Test that invalid types raise validation errors."""
    env_vars = {"REDIS_PORT": "not_a_number", "CACHE_TTL": "invalid"}

    with patch.dict(os.environ, env_vars):
        with pytest.raises(ValueError):
            Settings()


def test_redis_url_priority_over_components():
    """Test that REDIS_URL takes priority over individual components."""
    env_vars = {
        "REDIS_URL": "redis://priority.com:6379/1",
        "REDIS_HOST": "should_be_ignored.com",
        "REDIS_PORT": "9999",
        "REDIS_PASSWORD": "ignored_password",
    }

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        # Individual components should still be set
        assert settings.redis_host == "should_be_ignored.com"
        assert settings.redis_port == 9999
        assert settings.redis_password == "ignored_password"

        # But connection URL should use the full URL
        assert settings.redis_connection_url == "redis://priority.com:6379/1"


def test_optional_fields_none_by_default():
    """Test that optional fields default to None."""
    settings = Settings()

    assert settings.redis_password is None
    assert settings.redis_url is None
