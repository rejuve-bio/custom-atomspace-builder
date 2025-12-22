"""Graph information generation and management service."""

import os
import json
import shutil
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import humanize
from ..config import settings
from ..models.schemas import GraphInfo, AnnotationSchema
from ..utils.file_utils import (
    get_directory_size, 
    count_files_in_directory, 
    get_latest_directory
)
from ..utils.schema_converter import generate_annotation_schema
from ..services.database_service import database_service


class GraphInfoService:
    """Service for managing graph information and metadata."""
    
    def __init__(self):
        self.base_output_dir = settings.base_output_dir
    
    async def generate_graph_info(self, job_id: str, writer_type: str) -> GraphInfo:
        """Generate comprehensive graph information for a job."""
        output_dir = self.get_job_output_dir(job_id)
        dataset_count = max(count_files_in_directory(output_dir) - 2, 0)
        
        metadata = await self._load_metadata(job_id)
        schema = await database_service.get_schema(job_id)
        
        total_vertices = metadata.get("totalVertices", {}).get("num", 0)
        total_edges = metadata.get("totalEdges", {}).get("num", 0)
        dir_size = get_directory_size(output_dir)
        
        # Process vertex statistics
        vertices_by_label = metadata.get("verticesByLabel", {})
        top_entities = [
            {"count": details["num"], "name": label}
            for label, details in vertices_by_label.items()
        ]
        top_entities.sort(key=lambda x: x["count"], reverse=True)
        
        # Process edge statistics
        edges_by_label = metadata.get("edgesByLabel", {})
        top_connections = [
            {"count": details["num"], "name": label}
            for label, details in edges_by_label.items()
        ]
        top_connections.sort(key=lambda x: x["count"], reverse=True)
        
        # Generate frequent relationships
        frequent_relationships = []
        for edge in schema.get("edge_labels", []):
            source = edge.get("source_label")
            target = edge.get("target_label")
            edge_name = edge.get("name")
            if source and target and edge_name:
                count = edges_by_label.get(edge_name, {}).get("num", 0)
                if count > 0:
                    frequent_relationships.append({
                        "count": count,
                        "entities": [source, target],
                        "relationship": edge_name
                    })
        frequent_relationships.sort(key=lambda x: x["count"], reverse=True)
        
        # Generate schema representation
        schema_nodes = [
            {"data": {"id": v["name"], "properties": v.get("properties", [])}}
            for v in schema.get("vertex_labels", [])
        ]
        
        schema_edges = [
            {"data": {"source": e["source_label"], "target": e["target_label"],
                     "possible_connections": [e["name"]]}}
            for e in schema.get("edge_labels", [])
        ]
        
        return GraphInfo(
            job_id=job_id,
            writer_type=writer_type,
            node_count=total_vertices,
            edge_count=total_edges,
            dataset_count=dataset_count,
            data_size=humanize.naturalsize(dir_size),
            imported_on=str(datetime.now(tz=timezone.utc)),
            top_entities=top_entities,
            top_connections=top_connections,
            frequent_relationships=[
                {"count": rel["count"], "entities": rel["entities"]}
                for rel in frequent_relationships
            ],
            schema={"nodes": schema_nodes, "edges": schema_edges}
        )
    
    async def save_graph_info(self, job_id: str, graph_info: GraphInfo):
        """Save graph information to database and update history."""
        # Save graph info to database
        await database_service.save_graph_info(graph_info)
        
        # Load existing history
        history = await self.get_history()
        
        # Add to history
        history["history"] = [graph_info.dict()] + history["history"]
        
        # Save history to database
        await database_service.save_history(history)
    
    async def get_graph_info(self, job_id: str) -> Optional[GraphInfo]:
        """Get graph information for a job."""
        graph_info_data = await database_service.get_graph_info(job_id)
        
        if graph_info_data:
            return GraphInfo(**graph_info_data)
        
        return None
    
    async def generate_annotation_schema(self, job_id: str) -> Optional[AnnotationSchema]:
        """Generate annotation schema for a job."""
        output_dir = self.get_job_output_dir(job_id)
        if not os.path.exists(output_dir):
            return None
        
        # Check if already exists
        annotation_data = await database_service.get_annotation_schema(job_id)
        if annotation_data:
            return AnnotationSchema(**annotation_data)
        
        # Generate new one
        schema_data = await database_service.get_schema(job_id)
        if not schema_data:
            return None
        
        annotation_schema_data = generate_annotation_schema(schema_data, job_id)
        await database_service.save_annotation_schema(job_id, annotation_schema_data)
        
        return AnnotationSchema(**annotation_schema_data)
    
    async def get_annotation_schema(self, job_id: str) -> Optional[AnnotationSchema]:
        """Get annotation schema for a job."""
        annotation_data = await database_service.get_annotation_schema(job_id)
        if annotation_data:
            return AnnotationSchema(**annotation_data)
        
        return None
    
    async def get_history(self) -> Dict[str, Any]:
        """Get job processing history."""
        return await database_service.get_history()
    
    async def clear_history(self) -> Dict[str, Any]:
        """Clear the history, reset selected job ID, and delete all output directories."""
        history = await database_service.clear_history()
        
        # Delete all directories inside output directory
        try:
            for item in os.listdir(self.base_output_dir):
                item_path = os.path.join(self.base_output_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"Deleted output directory: {item}")
        except Exception as e:
            print(f"Warning: Error deleting output directories: {e}")
        
        return history
    
    async def delete_job_history(self, job_id: str) -> Tuple[Dict[str, Any], bool]:
        """Delete a job from history and return updated history and if selected job was affected."""
        return await database_service.delete_job_from_history(job_id)
    
    async def get_selected_job_id(self) -> Optional[str]:
        """Get the currently selected job ID."""
        return await database_service.get_selected_job_id()
    
    async def save_selected_job_id(self, job_id: str):
        """Save the selected job ID."""
        await database_service.save_selected_job_id(job_id)
    
    def get_job_output_dir(self, job_id: str) -> str:
        """Get output directory path for a job."""
        return os.path.join(self.base_output_dir, job_id)
    
    async def get_writer_type_from_job(self, job_id: str) -> Optional[str]:
        """Get writer type from job metadata."""
        job_metadata = await database_service.get_job_metadata(job_id)
        if job_metadata:
            return job_metadata.get("writer_type", "metta")
        return None
    
    async def _load_metadata(self, job_id: str) -> Dict[str, Any]:
        """Load graph metadata from database."""
        metadata = await database_service.get_graph_metadata(job_id)
        return metadata if metadata else {}


# Global service instance
graph_info_service = GraphInfoService()