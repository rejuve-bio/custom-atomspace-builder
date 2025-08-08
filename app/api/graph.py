"""Graph information API endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..services.graph_info_service import graph_info_service
from ..models.schemas import GraphInfo, AnnotationSchema
from ..utils.helpers import get_job_id_to_use

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/kg-info/{job_id}", response_model=GraphInfo)
@router.get("/kg-info/", response_model=GraphInfo)
async def get_graph_info(job_id: str = None):
    """Get knowledge graph information for a specific job or the selected job."""
    empty_response = GraphInfo(
        job_id="",
        writer_type="metta",
        node_count=0,
        edge_count=0,
        dataset_count=0,
        data_size="0 B",
        imported_on="",
        top_entities=[],
        top_connections=[],
        frequent_relationships=[],
        schema={"nodes": [], "edges": []}
    )
    
    try:
        job_id = get_job_id_to_use(job_id)
        if not job_id:
            return empty_response
        
        # Try to get existing graph info
        graph_info = graph_info_service.get_graph_info(job_id)
        if graph_info:
            return graph_info
        
        # Generate new graph info if not found
        writer_type = graph_info_service.get_writer_type_from_job(job_id)
        if writer_type:
            graph_info = await graph_info_service.generate_graph_info(job_id, writer_type)
            graph_info_service.save_graph_info(job_id, graph_info)
            return graph_info
        
        return empty_response
        
    except Exception as e:
        print(f"Error in get_graph_info: {str(e)}")
        return empty_response


@router.get("/schema/{job_id}", response_model=AnnotationSchema)
@router.get("/schema/", response_model=AnnotationSchema)
async def get_annotation_schema(job_id: str = None):
    """Get annotation schema for a specific job or the selected job."""
    empty_response = AnnotationSchema(job_id="", nodes=[], edges=[])
    
    try:
        job_id = get_job_id_to_use(job_id)
        if not job_id:
            return empty_response
        
        # Try to get existing annotation schema
        annotation_schema = graph_info_service.get_annotation_schema(job_id)
        if annotation_schema:
            return annotation_schema
        
        # Generate new annotation schema if not found
        annotation_schema = graph_info_service.generate_annotation_schema(job_id)
        if annotation_schema:
            return annotation_schema
        
        return empty_response
        
    except Exception as e:
        print(f"Error in get_annotation_schema: {str(e)}")
        return empty_response