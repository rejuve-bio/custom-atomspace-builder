import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .core.database import neo4j_manager
from .core.background_tasks import session_cleanup_worker

# Import routers
from .api.upload import router as upload_router
from .api.jobs import router as jobs_router
from .api.graph import router as graph_router
from .api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting AtomSpace Builder API...")
    
    # Initialize Neo4j connection
    neo4j_manager.initialize_driver()
    
    # Start background tasks
    cleanup_task = asyncio.create_task(session_cleanup_worker())
    
    print("AtomSpace Builder API started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down AtomSpace Builder API...")
    
    # Cancel background tasks
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    # Close database connections
    neo4j_manager.close_driver()
    
    print("AtomSpace Builder API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Custom AtomSpace Builder API",
        description="A refactored API for building knowledge graphs using HugeGraph",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    # Include routers
    app.include_router(upload_router)
    app.include_router(jobs_router)
    app.include_router(graph_router)
    app.include_router(admin_router)
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)