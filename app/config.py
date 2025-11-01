"""
Configuration settings for the Todo List API application.
Uses Pydantic BaseSettings for environment variable management.
"""

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Application settings
    app_name: str = "Todo List Mini Web"
    log_level: str = "INFO"
    
    # Database settings
    database_url: str = Field(
        default="sqlite:///./todos.db",
        description="SQLite database file path"
    )
    
    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0
    redis_url: str | None = None
    
    # Cache settings
    cache_ttl: int = Field(
        default=30,
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