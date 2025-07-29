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
    load_json_file, 
    save_json_file,
    get_latest_directory
)
from ..utils.schema_converter import generate_annotation_schema


class GraphInfoService:
    """Service for managing graph information and metadata."""
    
    def __init__(self):
        self.base_output_dir = settings.base_output_dir
        self.selected_job_file = settings.selected_job_file
        self.history_file = os.path.join(self.base_output_dir, "history.json")
    
    async def generate_graph_info(self, job_id: str, writer_type: str) -> GraphInfo:
        """Generate comprehensive graph information for a job."""
        output_dir = self.get_job_output_dir(job_id)
        dataset_count = max(count_files_in_directory(output_dir) - 2, 0)
        schema_path = os.path.join(output_dir, "schema.json")
        
        metadata = self._load_metadata(output_dir)
        schema = load_json_file(schema_path)
        
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
    
    def save_graph_info(self, job_id: str, graph_info: GraphInfo):
        """Save graph information to files and update history."""
        output_dir = self.get_job_output_dir(job_id)
        info_path = os.path.join(output_dir, "graph_info.json")
        
        # Load existing history
        history = self.get_history()
        
        # Add to history
        history["history"] = [graph_info.dict()] + history["history"]
        
        # Save both files
        save_json_file(self.history_file, history)
        save_json_file(info_path, graph_info.dict())
    
    def get_graph_info(self, job_id: str) -> Optional[GraphInfo]:
        """Get graph information for a job."""
        output_dir = self.get_job_output_dir(job_id)
        if not os.path.exists(output_dir):
            return None
        
        info_path = os.path.join(output_dir, "graph_info.json")
        graph_info_data = load_json_file(info_path)
        
        if graph_info_data:
            return GraphInfo(**graph_info_data)
        
        return None
    
    def generate_annotation_schema(self, job_id: str) -> Optional[AnnotationSchema]:
        """Generate annotation schema for a job."""
        output_dir = self.get_job_output_dir(job_id)
        schema_path = os.path.join(output_dir, "schema.json")
        annotation_path = os.path.join(output_dir, "annotation_schema.json")
        
        if not os.path.exists(output_dir) or not os.path.exists(schema_path):
            return None
        
        # Check if already exists
        annotation_data = load_json_file(annotation_path)
        if annotation_data:
            return AnnotationSchema(**annotation_data)
        
        # Generate new one
        schema_data = load_json_file(schema_path)
        if not schema_data:
            return None
        
        annotation_schema_data = generate_annotation_schema(schema_data, job_id)
        save_json_file(annotation_path, annotation_schema_data)
        
        return AnnotationSchema(**annotation_schema_data)
    
    def get_annotation_schema(self, job_id: str) -> Optional[AnnotationSchema]:
        """Get annotation schema for a job."""
        output_dir = self.get_job_output_dir(job_id)
        annotation_path = os.path.join(output_dir, "annotation_schema.json")
        
        annotation_data = load_json_file(annotation_path)
        if annotation_data:
            return AnnotationSchema(**annotation_data)
        
        return None
    
    def get_history(self) -> Dict[str, Any]:
        """Get job processing history."""
        history = load_json_file(self.history_file)
        if not history:
            history = {"selected_job_id": "", "history": []}
        
        return history
    
    def clear_history(self) -> Dict[str, Any]:
        """Clear the history file, reset selected job ID, and delete all output directories."""
        history = {"selected_job_id": "", "history": []}
        
        save_json_file(self.history_file, history)
        
        if os.path.exists(self.selected_job_file):
            os.remove(self.selected_job_file)
        
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
    
    def delete_job_history(self, job_id: str) -> Tuple[Dict[str, Any], bool]:
        """Delete a job from history and return updated history and if selected job was affected."""
        history = self.get_history()
        selected_job_affected = False
        
        selected_job_id = self.get_selected_job_id()
        if selected_job_id == job_id:
            selected_job_affected = True
            if os.path.exists(self.selected_job_file):
                os.remove(self.selected_job_file)
        
        original_count = len(history["history"])
        history["history"] = [item for item in history["history"] if item.get("job_id") != job_id]
        
        if len(history["history"]) != original_count or selected_job_affected:
            if selected_job_affected:
                history["selected_job_id"] = ""
            save_json_file(self.history_file, history)
        
        return history, selected_job_affected
    
    def get_selected_job_id(self) -> Optional[str]:
        """Get the currently selected job ID."""
        if not os.path.exists(self.selected_job_file):
            return None
        try:
            with open(self.selected_job_file, 'r') as f:
                return f.read().strip()
        except Exception:
            return None
    
    def save_selected_job_id(self, job_id: str):
        """Save the selected job ID."""
        os.makedirs(os.path.dirname(self.selected_job_file), exist_ok=True)
        try:
            with open(self.selected_job_file, 'w') as f:
                f.write(job_id)
        except Exception as e:
            print(f"Error saving selected job ID: {e}")
    
    def get_job_output_dir(self, job_id: str) -> str:
        """Get output directory path for a job."""
        return os.path.join(self.base_output_dir, job_id)
    
    def get_writer_type_from_job(self, job_id: str) -> Optional[str]:
        """Get writer type from job metadata."""
        job_metadata_path = os.path.join(self.get_job_output_dir(job_id), "job_metadata.json")
        job_metadata = load_json_file(job_metadata_path)
        return job_metadata.get("writer_type", "metta")
    
    def _load_metadata(self, output_dir: str) -> Dict[str, Any]:
        """Load graph metadata from output directory."""
        metadata_file = os.path.join(output_dir, "graph_metadata.json")
        return load_json_file(metadata_file)


# Global service instance
graph_info_service = GraphInfoService()