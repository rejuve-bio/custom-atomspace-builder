"""General helper functions."""

import os
from typing import Optional
from fastapi import HTTPException
from ..config import settings
from ..utils.file_utils import get_latest_directory, load_json_file


def get_job_id_to_use(job_id: Optional[str] = None) -> Optional[str]:
    """Get the job ID to use based on priority: provided -> selected -> latest."""
    from ..services.graph_info_service import graph_info_service
    
    # Use provided job_id if valid
    if job_id and os.path.exists(graph_info_service.get_job_output_dir(job_id)):
        return job_id
    
    # Use selected job if valid
    selected_id = graph_info_service.get_selected_job_id()
    if selected_id and os.path.exists(graph_info_service.get_job_output_dir(selected_id)):
        return selected_id
    
    # Use latest job
    latest_dir = get_latest_directory(settings.base_output_dir)
    if latest_dir:
        return os.path.basename(latest_dir)
    
    return None


def get_writer_type_from_job(job_id: str) -> str:
    """Get writer type from job metadata with error handling."""
    from ..services.graph_info_service import graph_info_service
    
    try:
        writer_type = graph_info_service.get_writer_type_from_job(job_id)
        return writer_type if writer_type else "metta"
    except Exception as e:
        print(f"Error reading job metadata for {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading job metadata for {job_id}: {str(e)}"
        )


def validate_job_exists(job_id: str) -> bool:
    """Check if a job directory exists."""
    from ..services.graph_info_service import graph_info_service
    return os.path.exists(graph_info_service.get_job_output_dir(job_id))


def safe_remove_file(file_path: str) -> bool:
    """Safely remove a file with error handling."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"Warning: Could not remove file {file_path}: {e}")
    return False


def safe_create_directory(directory: str) -> bool:
    """Safely create a directory with error handling."""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error creating directory {directory}: {e}")
        return False