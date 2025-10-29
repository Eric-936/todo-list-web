"""
Configuration settings for the Todo List API application.
Uses Pydantic BaseSettings for environment variable management.
"""

import os
# from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # Application settings
    app_name: str = "Todo List Mini Web"
    # debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Database settings
    database_url: str = Field(
        default="sqlite:///./todos.db",
        env="DATABASE_URL",
        description="SQLite database file path"
    )
    
    # Redis settings
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: str | None = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_url: str | None = Field(default=None, env="REDIS_URL")
    
    # Cache settings
    cache_ttl: int = Field(
        default=30,
        env="CACHE_TTL",
        description="Cache TTL in seconds"
    )
    
    # # API settings
    # api_key: Optional[str] = Field(default=None, env="API_KEY")
    # cors_origins: list[str] = Field(
    #     default=["http://localhost:3000", "http://localhost:8000"],
    #     env="CORS_ORIGINS"
    # )
    
    # # Pagination defaults
    # default_page_size: int = Field(default=20, env="DEFAULT_PAGE_SIZE")
    # max_page_size: int = Field(default=100, env="MAX_PAGE_SIZE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def redis_connection_url(self) -> str:
        """Generate Redis connection URL."""
        if self.redis_url:
            return self.redis_url
        
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # @property
    # def is_development(self) -> bool:
    #     """Check if running in development mode."""
    #     return self.debug or os.getenv("ENVIRONMENT", "development").lower() == "development"


# Global settings instance
settings = Settings()