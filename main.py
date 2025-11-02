"""
Application entry point for production deployment.

TODO: Implement production entry point
- Import the FastAPI app from app.main
- Add any production-specific configuration
- Optional: Add application startup hooks
- This file serves as the entry point for ASGI servers like Uvicorn
- Keep it minimal - main logic should be in app/main.py

Usage:
  uvicorn main:app --host 0.0.0.0 --port 8000
  or
  uvicorn main:app --reload (for development)
"""


from app.database.database import get_db_health
from app.models.todo import Todo
from app.services.cache_service import CacheService

if __name__ == "__main__":
    # Example usage of get_db_health function
    print(CacheService().health_check())