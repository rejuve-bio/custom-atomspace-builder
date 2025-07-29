"""Job management API endpoints."""

import json
import os
import shutil
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from ..core.session_manager import session_manager
from ..services.hugegraph_service import hugegraph_service
from ..services.neo4j_service import neo4j_service
from ..services.annotation_service import annotation_service
from ..services.graph_info_service import graph_info_service
from ..models.schemas import (
    HugeGraphLoadResponse, 
    JobSelectionRequest,
    DeleteJobResponse,
    HistoryResponse,
    SchemaConversionResponse
)
from ..models.enums import WriterType
from ..utils.file_utils import get_output_files, create_zip_file
from ..utils.schema_converter import json_to_groovy
from ..utils.helpers import get_job_id_to_use, get_writer_type_from_job

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/load", response_model=HugeGraphLoadResponse)
async def load_data(
    session_id: str = Form(...),
    config: str = Form(...),
    schema_json: str = Form(...),
    writer_type: str = Form("metta")
):
    """Submit processing job using uploaded files from session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Invalid or expired session")
    
    if not session.uploaded_files:
        raise HTTPException(status_code=400, detail="No files uploaded in session")
    
    try:
        config_data = json.loads(config)
        schema_data = json.loads(schema_json)
        
        # Get session directory with uploaded files
        session_dir = session_manager._get_session_dir(session_id)
        
        # Process data using HugeGraph service
        response = await hugegraph_service.process_data(
            files_dir=session_dir,
            config_data=config_data,
            schema_data=schema_data,
            writer_type=writer_type
        )
        
        job_id = response.job_id
        output_dir = response.output_dir
        
        # Auto load to Neo4j if writer_type is neo4j
        neo4j_load_result = None
        if writer_type == WriterType.NEO4J:
            neo4j_load_result = await neo4j_service.load_data_to_neo4j(output_dir, job_id)
            
            # Save load results
            if neo4j_load_result:
                neo4j_result_path = os.path.join(output_dir, "neo4j_load_result.json")
                with open(neo4j_result_path, "w") as f:
                    json.dump(neo4j_load_result.dict(), f, indent=2)
        
        # Notify annotation service
        error_msg = await annotation_service.notify_annotation_service(job_id, writer_type)
        if error_msg:
            # Try to fallback to selected job
            selected_job_id = get_job_id_to_use()
            if selected_job_id:
                await annotation_service.notify_annotation_service(selected_job_id, writer_type)
            
            # Cleanup failed job
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail={"message": error_msg, "job_id": job_id})
        
        # Generate and save graph info
        graph_info = await graph_info_service.generate_graph_info(job_id, writer_type)
        graph_info_service.save_graph_info(job_id, graph_info)
        graph_info_service.save_selected_job_id(job_id)
        
        # Update response message
        success_message = f"Graph generated successfully using {writer_type} writer"
        if neo4j_load_result and neo4j_load_result.status == "success":
            success_message += " and loaded to Neo4j"
        
        response.message = success_message
        
        # Mark session as consumed and cleanup
        session_manager.consume_session(session_id)
        session_manager.cleanup_session(session_id)
        
        return response
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@router.post("/select-job")
async def select_job(request: JobSelectionRequest):
    """Select a job as the current active job."""
    job_id = request.job_id
    writer_type = get_writer_type_from_job(job_id)
    
    if not os.path.exists(graph_info_service.get_job_output_dir(job_id)):
        raise HTTPException(status_code=404, detail=f"Job ID {job_id} does not exist")
    
    error_msg = await annotation_service.notify_annotation_service(job_id, writer_type)
    if error_msg:
        raise HTTPException(status_code=500, detail=f"Error connecting annotation service: {error_msg}")
    
    graph_info_service.save_selected_job_id(job_id)
    return {"message": f"Job ID {job_id} selected successfully"}


@router.get("/history", response_model=HistoryResponse)
async def get_history():
    """Get job processing history."""
    history = graph_info_service.get_history()
    job_id = get_job_id_to_use()
    history["selected_job_id"] = job_id if job_id else ""
    return history


@router.get("/output/{job_id}")
async def get_output(job_id: str):
    """Download all output files for a job as ZIP."""
    output_dir = graph_info_service.get_job_output_dir(job_id)
    
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail=f"No output files found for job ID: {job_id}")
    
    files = get_output_files(output_dir)
    if not files:
        raise HTTPException(status_code=404, detail=f"No output files found for job ID: {job_id}")
    
    zip_bytes = create_zip_file(files)
    return StreamingResponse(
        zip_bytes, 
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=output-{job_id}.zip"}
    )


@router.get("/output-file/{job_id}/{filename}")
async def get_output_file(job_id: str, filename: str):
    """Download a specific output file."""
    file_path = os.path.join(graph_info_service.get_job_output_dir(job_id), filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename} for job ID: {job_id}")
    
    return FileResponse(file_path, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.post("/convert-schema", response_model=SchemaConversionResponse)
async def convert_schema(schema_json: dict = None):
    """Convert JSON schema to Groovy format."""
    try:
        groovy_schema = json_to_groovy(schema_json)
        return SchemaConversionResponse(status="success", schema_groovy=groovy_schema)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error converting schema: {str(e)}")


@router.delete("/delete-job/{job_id}", response_model=DeleteJobResponse)
async def delete_job(job_id: str):
    """Delete a job and its associated data."""
    writer_type = get_writer_type_from_job(job_id)

    # Delete from Neo4j if applicable
    if writer_type == WriterType.NEO4J:
        neo4j_service.delete_subgraph(job_id)
    
    # Update history
    updated_history, selected_job_affected = graph_info_service.delete_job_history(job_id)
    
    # Delete job directory
    job_dir = graph_info_service.get_job_output_dir(job_id)
    dir_deleted = False
    new_selected_job = None
    
    if os.path.exists(job_dir):
        try:
            shutil.rmtree(job_dir)
            dir_deleted = True
        except Exception as e:
            print(f"Warning: Could not delete job directory {job_dir}: {e}")
    
    # Select new job if current was deleted
    if selected_job_affected and updated_history["history"]:
        try:
            new_job_id = updated_history["history"][0]["job_id"]
            await select_job(JobSelectionRequest(job_id=new_job_id))
            new_selected_job = new_job_id
            updated_history["selected_job_id"] = new_job_id
        except Exception as e:
            print(f"Warning: Could not select new job: {e}")
    
    # Build response message
    message_parts = ["Job removed from history"]
    if dir_deleted:
        message_parts.append("job directory deleted")
    if selected_job_affected:
        if new_selected_job:
            message_parts.append(f"selected job set to {new_selected_job}")
        else:
            message_parts.append("selected job was reset")
    
    updated_history["selected_job_id"] = get_job_id_to_use()
    
    return DeleteJobResponse(
        message=", ".join(message_parts),
        history=updated_history,
        directory_deleted=dir_deleted,
        selected_job_affected=selected_job_affected,
        new_selected_job=new_selected_job
    )