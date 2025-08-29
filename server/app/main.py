"""
Main FastAPI application for Talk to DB.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.api.routes import auth, keys, connections, schema, query, history
from app.db.base import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    init_db()
    print("🚀 Starting Talk to DB Server...")
    yield
    # Shutdown
    print("👋 Shutting down Talk to DB Server...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="Talk to DB API",
        description="AI Agent for talking to databases via natural language",
        version="0.1.0",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )
    
    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    if settings.app_env == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com"]
        )
    
    # Include routers
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(keys.router, prefix="/api/keys", tags=["API Keys"])
    app.include_router(connections.router, prefix="/api/connections", tags=["Database Connections"])
    app.include_router(schema.router, prefix="/api/schema", tags=["Database Schema"])
    app.include_router(query.router, prefix="/api/query", tags=["Query Generation & Execution"])
    app.include_router(history.router, prefix="/api/history", tags=["Query History"])
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Talk to DB API",
            "version": "0.1.0",
            "docs": "/docs",
            "status": "running"
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": "2025-01-26T10:00:00Z"}
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower()
    )
