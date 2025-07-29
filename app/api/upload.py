"""Upload-related API endpoints."""

import os
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from ..core.session_manager import session_manager
from ..models.schemas import (
    CreateSessionResponse, 
    UploadResponse, 
    SessionStatusResponse,
    UploadFileInfo
)

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/create-session", response_model=CreateSessionResponse)
async def create_upload_session():
    """Create a new upload session."""
    session_id = session_manager.create_session()
    session = session_manager.get_session(session_id)
    
    return CreateSessionResponse(
        session_id=session_id,
        expires_at=session.expires_at.isoformat(),
        upload_url=f"/api/upload/files"
    )


@router.post("/files", response_model=UploadResponse)
async def upload_files(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Upload files to a specific session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session_dir = os.path.join(
        session_manager._get_session_dir(session_id)
    )
    uploaded_files = []
    
    for file in files:
        # Check for duplicate filenames
        if file.filename in session.uploaded_files:
            raise HTTPException(
                status_code=400, 
                detail=f"File {file.filename} already uploaded"
            )
        
        file_path = os.path.join(session_dir, file.filename)
        
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Add to session
            session_manager.add_file_to_session(session_id, file.filename)
            
            uploaded_files.append(UploadFileInfo(
                filename=file.filename,
                size=len(content),
                uploaded_at=datetime.now(tz=timezone.utc).isoformat()
            ))
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to upload {file.filename}: {str(e)}"
            )
    
    return UploadResponse(
        session_id=session_id,
        uploaded_files=uploaded_files,
        total_files=len(session.uploaded_files),
        files_in_session=session.uploaded_files
    )


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_upload_status(session_id: str):
    """Get upload session status and file list."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    file_details = session_manager.get_session_files_info(session_id)
    
    return SessionStatusResponse(
        session_id=session_id,
        status=session.status,
        expires_at=session.expires_at.isoformat(),
        files=file_details,
        total_files=len(file_details)
    )


@router.delete("/{session_id}/files/{filename}")
async def delete_uploaded_file(session_id: str, filename: str):
    """Remove a file from upload session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    if filename not in session.uploaded_files:
        raise HTTPException(status_code=404, detail="File not found in session")
    
    success = session_manager.remove_file_from_session(session_id, filename)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove file")
    
    return {"message": f"File {filename} removed successfully"}