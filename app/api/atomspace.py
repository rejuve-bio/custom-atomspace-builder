from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Any, Optional
from ..services.atomspace_service import atomspace_service

router = APIRouter(
    prefix="/api/atomspace",
    tags=["AtomSpace"],
)

class MeTTaScript(BaseModel):
    script: str

class MeTTAResponse(BaseModel):
    status: str
    results: List[List[str]]
    error: Optional[str] = None

@router.post("/execute", response_model=MeTTAResponse)
async def execute_metta(data: MeTTaScript):
    try:
        results = atomspace_service.execute_script(data.script)
        return MeTTAResponse(status="success", results=results)
    except Exception as e:
        return MeTTAResponse(status="error", results=[], error=str(e))

@router.post("/load")
async def load_file(file_path: str):
    success = atomspace_service.load_metta_file(file_path)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to load file. Check logs/paths.")
    return {"status": "success", "message": f"File {file_path} loaded successfully."}

@router.get("/health")
async def health_check():
    return {"status": "active", "engine": "Hyperon/MeTTa"}
