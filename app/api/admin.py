"""Admin API endpoints."""

from fastapi import APIRouter
from ..core.database import neo4j_manager
from ..services.graph_info_service import graph_info_service
from ..models.schemas import HealthResponse, HistoryResponse
from ..config import settings

router = APIRouter(prefix="/api", tags=["admin"])


@router.delete("/clear-history", response_model=HistoryResponse)
async def clear_history_endpoint():
    """Clear all job history and output directories."""
    history = graph_info_service.clear_history()
    return HistoryResponse(
        selected_job_id=history["selected_job_id"],
        history=history["history"]
    )


@router.get("/neo4j/config")
async def get_neo4j_config():
    """Get Neo4j configuration (with masked password)."""
    safe_config = settings.neo4j_config.copy()
    safe_config["password"] = "***"
    return safe_config


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "ok",
        "neo4j_connected": neo4j_manager.is_connected(),
        "annotation_service_url": settings.annotation_service_url is not None
    }
    return health_status


@router.get("/config")
async def get_config():
    """Get application configuration (sanitized)."""
    return {
        "hugegraph_host": settings.hugegraph_host,
        "hugegraph_port": settings.hugegraph_port,
        "hugegraph_graph": settings.hugegraph_graph,
        "base_output_dir": settings.base_output_dir,
        "session_timeout_hours": settings.session_timeout.total_seconds() / 3600,
        "annotation_service_configured": settings.annotation_service_url is not None,
        "neo4j_host": settings.neo4j_config["host"],
        "neo4j_port": settings.neo4j_config["port"],
        "neo4j_database": settings.neo4j_config["database"]
    }