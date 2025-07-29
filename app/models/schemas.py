"""Pydantic models for the AtomSpace Builder API."""

from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
from .enums import WriterType


class PropertyKey(BaseModel):
    name: str
    type: str
    cardinality: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class VertexLabel(BaseModel):
    name: str
    properties: List[str]
    primary_keys: Optional[List[str]] = None
    nullable_keys: Optional[List[str]] = None
    id_strategy: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class EdgeLabel(BaseModel):
    name: str
    source_label: str
    target_label: str
    properties: Optional[List[str]] = None
    sort_keys: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None


class SchemaDefinition(BaseModel):
    property_keys: List[PropertyKey]
    vertex_labels: List[VertexLabel]
    edge_labels: List[EdgeLabel]


class HugeGraphLoadResponse(BaseModel):
    job_id: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None
    output_dir: Optional[str] = None
    schema_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    writer_type: Optional[str] = None


class JobSelectionRequest(BaseModel):
    job_id: str


class UploadSession(BaseModel):
    session_id: str
    created_at: datetime
    expires_at: datetime
    uploaded_files: List[str] = []
    status: str = "active"  # active, expired, consumed
    metadata: Dict[str, Any] = {}


class UploadFileInfo(BaseModel):
    filename: str
    size: int
    uploaded_at: str


class UploadResponse(BaseModel):
    session_id: str
    uploaded_files: List[UploadFileInfo]
    total_files: int
    files_in_session: List[str]


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    expires_at: str
    files: List[Dict[str, Any]]
    total_files: int


class CreateSessionResponse(BaseModel):
    session_id: str
    expires_at: str
    upload_url: str


class GraphInfo(BaseModel):
    job_id: str
    writer_type: str
    node_count: int
    edge_count: int
    dataset_count: int
    data_size: str
    imported_on: str
    top_entities: List[Dict[str, Any]]
    top_connections: List[Dict[str, Any]]
    frequent_relationships: List[Dict[str, Any]]
    schema: Dict[str, Any]


class AnnotationSchema(BaseModel):
    job_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class JobMetadata(BaseModel):
    job_id: str
    writer_type: str
    created_at: str
    neo4j_config: Optional[Dict[str, Any]] = None


class Neo4jLoadResult(BaseModel):
    status: str
    job_id: Optional[str] = None
    tenant_id: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class DeleteJobResponse(BaseModel):
    message: str
    history: Dict[str, Any]
    directory_deleted: bool
    selected_job_affected: bool
    new_selected_job: Optional[str] = None


class HistoryResponse(BaseModel):
    selected_job_id: str
    history: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str


class SchemaConversionResponse(BaseModel):
    status: str
    schema_groovy: str