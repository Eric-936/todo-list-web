"""
Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.database import init_db
from app.routers import todos


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    API app lifespan context manager.
    Handles startup and shutdown events.
    """
    # Log startup
    logger.info("Starting Todo List API...")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Application is ready
    logger.info("Todo List API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Todo List API...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="A simple Todo List API with caching support",
    version="0.1.0",
    lifespan=lifespan,
)


# Setup templates
templates = Jinja2Templates(directory="templates")


# Allow CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Global HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "status_code": 500}
    )


# Include routers
app.include_router(todos.router, prefix="/api")


# Web interface endpoint
@app.get("/", tags=["web"])
async def web_interface(request: Request):
    """Serve the web interface."""
    return templates.TemplateResponse("index.html", {"request": request})


# # API root endpoint
# @app.get("/api", tags=["root"])
# async def api_root():
#     """API root endpoint."""
#     return {
#         "message": "Welcome to Todo List API",
#         "version": "1.0.0",
#         "docs": "/docs",
#         "health": "/api/todos/health",
#     }


# # Simple health check endpoint at root level
# @app.get("/healthz", tags=["health"])
# async def healthz():
#     """Simple health check endpoint."""
#     return {"status": "ok", "service": "todo-list-api"}
