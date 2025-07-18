from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
from neo4j import GraphDatabase
from dotenv import load_dotenv
import json
import shutil
import tempfile
import subprocess
import os
import glob
import uuid
import zipfile
import io
import humanize
import httpx
import yaml
import secrets

load_dotenv()

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

HUGEGRAPH_LOADER_PATH = config['paths']['hugegraph_loader']
HUGEGRAPH_HOST = os.getenv('HUGEGRAPH_HOST')
HUGEGRAPH_PORT = os.getenv('HUGEGRAPH_PORT')
HUGEGRAPH_GRAPH = os.getenv('HUGEGRAPH_GRAPH')
BASE_OUTPUT_DIR = os.path.abspath(config['paths']['output_dir'])
ANNOTATION_SERVICE_URL = os.getenv('ANNOTATION_SERVICE_URL')
ANNOTATION_SERVICE_TIMEOUT = float(os.getenv('ANNOTATION_SERVICE_TIMEOUT'))
SELECTED_JOB_FILE = os.path.join(BASE_OUTPUT_DIR, "selected_job.txt")
SESSION_TIMEOUT = timedelta(hours=2) 

# For future: use redis session management
upload_sessions = {}

NEO4J_CONFIG = {
    "host": os.getenv('NEO4J_HOST'),
    "port": int(os.getenv('NEO4J_PORT')),
    "username": os.getenv('NEO4J_USERNAME'),
    "password": os.getenv('NEO4J_PASSWORD'),
    "database": os.getenv('NEO4J_DATABASE')
}

def initialize_neo4j_driver():
    global neo4j_driver
    try:
        neo4j_driver = GraphDatabase.driver(
            f"bolt://{NEO4J_CONFIG['host']}:{NEO4J_CONFIG['port']}", 
            auth=(NEO4J_CONFIG['username'], NEO4J_CONFIG['password']),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_timeout=10,
            encrypted=False
        )
        # Test connection
        with neo4j_driver.session() as session:
            session.run("RETURN 1").consume()
        print("Neo4j driver initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize Neo4j driver: {e}")
        print("Neo4j features will be disabled until connection is restored")
        return False

neo4j_driver = None
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    initialize_neo4j_driver()
    yield
    # Shutdown
    if neo4j_driver:
        neo4j_driver.close()
        print("Neo4j driver closed")

app = FastAPI(title="Custom AtomSpace Builder API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config['cors']['allow_origins'],
    allow_credentials=config['cors']['allow_credentials'],
    allow_methods=config['cors']['allow_methods'],
    allow_headers=config['cors']['allow_headers'],
)

class WriterType(str, Enum):
    METTA = "metta"
    NEO4J = "neo4j"

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

def create_upload_session() -> str:
    session_id = secrets.token_urlsafe(32)
    session = UploadSession(
        session_id=session_id,
        created_at=datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + SESSION_TIMEOUT,
        uploaded_files=[],
        status="active"
    )
    upload_sessions[session_id] = session
    return session_id

def get_upload_session(session_id: str) -> Optional[UploadSession]:
    session = upload_sessions.get(session_id)
    if session and session.expires_at > datetime.now(tz=timezone.utc):
        return session
    elif session:
        session.status = "expired"
    return None

def json_to_groovy(schema_json: Union[Dict, SchemaDefinition]) -> str:
    if isinstance(schema_json, dict):
        schema = SchemaDefinition(**schema_json)
    else:
        schema = schema_json
    
    groovy_lines = []
    
    for prop in schema.property_keys:
        line = f'schema.propertyKey("{prop.name}").as{prop.type.capitalize()}()'
        if prop.cardinality:
            line += f'.cardinality("{prop.cardinality}")'
        if prop.options:
            for opt_name, opt_value in prop.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    groovy_lines.append("")
    
    for vertex in schema.vertex_labels:
        line = f'schema.vertexLabel("{vertex.name}")'
        if vertex.id_strategy:
            if vertex.id_strategy == "primary_key":
                line += '.useCustomizeStringId()'
            elif vertex.id_strategy == "customize_number":
                line += '.useCustomizeNumberId()'
            elif vertex.id_strategy == "customize_string":
                line += '.useCustomizeStringId()'
            elif vertex.id_strategy == "automatic":
                line += '.useAutomaticId()'
        if vertex.properties:
            props_str = ', '.join([f'"{prop}"' for prop in vertex.properties])
            line += f'.properties({props_str})'
        if vertex.primary_keys:
            keys_str = ', '.join([f'"{key}"' for key in vertex.primary_keys])
            line += f'.primaryKeys({keys_str})'
        if vertex.nullable_keys:
            keys_str = ', '.join([f'"{key}"' for key in vertex.nullable_keys])
            line += f'.nullableKeys({keys_str})'
        if vertex.options:
            for opt_name, opt_value in vertex.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    groovy_lines.append("")
    
    for edge in schema.edge_labels:
        line = f'schema.edgeLabel("{edge.name}")'
        line += f'.sourceLabel("{edge.source_label}")'
        line += f'.targetLabel("{edge.target_label}")'
        if edge.properties:
            props_str = ', '.join([f'"{prop}"' for prop in edge.properties])
            line += f'.properties({props_str})'
        if edge.sort_keys:
            keys_str = ', '.join([f'"{key}"' for key in edge.sort_keys])
            line += f'.sortKeys({keys_str})'
        if edge.options:
            for opt_name, opt_value in edge.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    return '\n'.join(groovy_lines)

def update_file_paths_in_config(config, file_mapping):
    updated_config = json.loads(json.dumps(config))
    
    def update_paths(items):
        for item in items:
            if "input" in item and item["input"].get("type") == "file":
                original_path = item["input"]["path"]
                filename = os.path.basename(original_path)
                if filename in file_mapping:
                    item["input"]["path"] = file_mapping[filename]
        return items
    
    if "vertices" in updated_config:
        updated_config["vertices"] = update_paths(updated_config["vertices"])
    if "edges" in updated_config:
        updated_config["edges"] = update_paths(updated_config["edges"])
    
    return updated_config

def get_job_output_dir(job_id):
    return os.path.join(BASE_OUTPUT_DIR, job_id)

def get_output_files(output_dir):
    if not os.path.exists(output_dir):
        return []
    return [os.path.join(output_dir, f) for f in os.listdir(output_dir) 
            if os.path.isfile(os.path.join(output_dir, f))]

def create_zip_file(files):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for file_path in files:
            zf.write(file_path, arcname=os.path.basename(file_path))
    memory_file.seek(0)
    return memory_file

def load_metadata(output_dir):
    metadata_file = os.path.join(output_dir, "graph_metadata.json")
    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_graph_info(job_id: str, graph_info: dict):
    output_dir = get_job_output_dir(job_id)
    info_path = os.path.join(output_dir, "graph_info.json")
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    
    if os.path.exists(history_path):
        with open(history_path, 'r') as f:
            history = json.load(f)
    else:
        history = {"selected_job_id": "", "history": []}
    
    history["history"] = [graph_info] + history["history"]
    
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    with open(info_path, 'w') as f:
        json.dump(graph_info, f, indent=2)

def get_directory_size(directory: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total

def count_files_in_directory(directory: str) -> int:
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return 0
    try:
        return len([f for f in os.listdir(directory) 
                   if os.path.isfile(os.path.join(directory, f))])
    except Exception:
        return 0

def get_selected_job_id() -> Optional[str]:
    if not os.path.exists(SELECTED_JOB_FILE):
        return None
    try:
        with open(SELECTED_JOB_FILE, 'r') as f:
            return f.read().strip()
    except Exception:
        return None

def save_selected_job_id(job_id: str):
    os.makedirs(os.path.dirname(SELECTED_JOB_FILE), exist_ok=True)
    try:
        with open(SELECTED_JOB_FILE, 'w') as f:
            f.write(job_id)
    except Exception as e:
        print(f"Error saving selected job ID: {e}")

def get_latest_job_dir() -> Optional[str]:
    job_dirs = glob.glob(os.path.join(BASE_OUTPUT_DIR, "*"))
    if not job_dirs:
        return None
    job_dirs.sort(key=os.path.getmtime, reverse=True)
    return job_dirs[0]

def get_job_id_to_use(job_id: Optional[str] = None) -> Optional[str]:
    if job_id and os.path.exists(get_job_output_dir(job_id)):
        return job_id
    
    selected_id = get_selected_job_id()
    if selected_id and os.path.exists(get_job_output_dir(selected_id)):
        return selected_id
    
    latest_dir = get_latest_job_dir()
    if latest_dir:
        return os.path.basename(latest_dir)
    
    return None

async def generate_graph_info(job_id: str, writer_type: str) -> dict:
    output_dir = get_job_output_dir(job_id)
    dataset_count = max(count_files_in_directory(output_dir) - 2, 0)
    schema_path = os.path.join(output_dir, "schema.json")
    
    metadata = load_metadata(output_dir)

    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    total_vertices = metadata.get("totalVertices", {}).get("num", 0)
    total_edges = metadata.get("totalEdges", {}).get("num", 0)
    dir_size = get_directory_size(output_dir)
    
    vertices_by_label = metadata.get("verticesByLabel", {})
    top_entities = [{"count": details["num"], "name": label}
                   for label, details in vertices_by_label.items()]
    top_entities.sort(key=lambda x: x["count"], reverse=True)
    
    edges_by_label = metadata.get("edgesByLabel", {})
    top_connections = [{"count": details["num"], "name": label}
                      for label, details in edges_by_label.items()]
    top_connections.sort(key=lambda x: x["count"], reverse=True)
    
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
    
    schema_nodes = [{"data": {"id": v["name"], "properties": v.get("properties", [])}}
                   for v in schema.get("vertex_labels", [])]
    
    schema_edges = [{"data": {"source": e["source_label"], "target": e["target_label"],
                             "possible_connections": [e["name"]]}}
                   for e in schema.get("edge_labels", [])]
    
    return {
        "job_id": job_id,
        "writer_type": writer_type,
        "node_count": total_vertices,
        "edge_count": total_edges,
        "dataset_count": dataset_count,
        "data_size": humanize.naturalsize(dir_size),
        "imported_on": str(datetime.now(tz=timezone.utc)),
        "top_entities": top_entities,
        "top_connections": top_connections,
        "frequent_relationships": [{"count": rel["count"], "entities": rel["entities"]}
                                 for rel in frequent_relationships],
        "schema": {"nodes": schema_nodes, "edges": schema_edges}
    }



def generate_annotation_schema(schema_data: dict, job_id: str) -> dict:
    annotation_schema = {"job_id": job_id, "nodes": [], "edges": []}
    
    for vertex in schema_data.get("vertex_labels", []):
        annotation_schema["nodes"].append({
            "id": vertex["name"],
            "name": vertex["name"],
            "category": "entity",
            "inputs": [{"label": prop, "name": prop, "inputType": "input"}
                      for prop in vertex.get("properties", [])]
        })
    
    for i, edge in enumerate(schema_data.get("edge_labels", []), 1):
        annotation_schema["edges"].append({
            "id": str(i),
            "source": edge["source_label"],
            "target": edge["target_label"],
            "label": edge["name"]
        })
    
    return annotation_schema

async def notify_annotation_service(job_id: str) -> Optional[str]:
    payload = {"folder_id": job_id}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ANNOTATION_SERVICE_URL,
                json=payload,
                timeout=ANNOTATION_SERVICE_TIMEOUT
            )
            if response.status_code != 200:
                error_msg = f"Annotation service returned {response.status_code}: {response.text}"
                print(f"Warning: {error_msg}")
                return error_msg
    except httpx.TimeoutException:
        error_msg = "Timeout connecting to annotation service"
        print(f"Warning: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Failed to connect to annotation service: {str(e)}"
        print(f"Warning: {error_msg}")
        return error_msg
    
    return None

def clear_history():
    """Clear the history file, reset selected job ID, and delete all output directories"""
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    history = {"selected_job_id": "", "history": []}
    
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    
    if os.path.exists(SELECTED_JOB_FILE):
        os.remove(SELECTED_JOB_FILE)
    
    # Delete all directories inside output directory
    try:
        for item in os.listdir(BASE_OUTPUT_DIR):
            item_path = os.path.join(BASE_OUTPUT_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"Deleted output directory: {item}")
    except Exception as e:
        print(f"Warning: Error deleting output directories: {e}")
    
    return history


def delete_job_history(job_id: str):
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    selected_job_affected = False
    
    if not os.path.exists(history_path):
        return {"selected_job_id": "", "history": []}, selected_job_affected
    
    with open(history_path, 'r') as f:
        history = json.load(f)
    
    selected_job_id = get_selected_job_id()
    if selected_job_id == job_id:
        selected_job_affected = True
        if os.path.exists(SELECTED_JOB_FILE):
            os.remove(SELECTED_JOB_FILE)
    
    original_count = len(history["history"])
    history["history"] = [item for item in history["history"] if item.get("job_id") != job_id]
    
    if len(history["history"]) != original_count or selected_job_affected:
        if selected_job_affected:
            history["selected_job_id"] = ""
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
    
    return history, selected_job_affected

async def load_data_to_neo4j(output_dir: str, job_id: str) -> dict:
    """Load generated CSV files to Neo4j using Cypher scripts"""
    if not neo4j_driver:
        return {"status": "error", "message": "Neo4j driver not initialized"}
    
    try:
        # Step 1: Copy CSV files to job-specific directory
        csv_copy_result = copy_csv_files_to_neo4j(output_dir, job_id)
        if not csv_copy_result["success"]:
            return {"status": "error", "message": csv_copy_result["message"]}
        
        with neo4j_driver.session() as session:
            # Find all cypher files
            node_files = sorted(Path(output_dir).glob("nodes_*.cypher"))
            edge_files = sorted(Path(output_dir).glob("edges_*.cypher"))
            
            results = {"nodes_loaded": 0, "edges_loaded": 0, "files_processed": []}
            
            # Process node files first
            for file_path in node_files:
                result = execute_cypher_file(session, file_path, job_id)
                if result["success"]:
                    results["nodes_loaded"] += result.get("total", 0)
                    results["files_processed"].append(str(file_path.name))
            
            # Process edge files second
            for file_path in edge_files:
                result = execute_cypher_file(session, file_path, job_id)
                if result["success"]:
                    results["edges_loaded"] += result.get("total", 0)
                    results["files_processed"].append(str(file_path.name))
            
            # Step 3: Cleanup import files after successful loading
            cleanup_neo4j_import_files(job_id)
            
            return {
                "status": "success",
                "job_id": job_id,
                "tenant_id": job_id,
                "results": results
            }
            
    except Exception as e:
        # Try to cleanup even if loading failed
        cleanup_neo4j_import_files(job_id)
        return {"status": "error", "message": str(e)}

def copy_csv_files_to_neo4j(output_dir: str, job_id: str, container_name: str = "neo4j-atomspace") -> dict:
    """Copy CSV files to Neo4j container import/job_id directory"""
    try:
        csv_files = list(Path(output_dir).glob("*.csv"))
        if not csv_files:
            return {"success": False, "message": "No CSV files found"}
        
        # Create job-specific directory in Neo4j import
        mkdir_cmd = f"docker exec {container_name} mkdir -p /var/lib/neo4j/import/{job_id}"
        os.system(mkdir_cmd)
        
        copied_files = []
        for csv_file in csv_files:
            # Copy file to job-specific directory
            copy_cmd = f"docker cp {csv_file} {container_name}:/var/lib/neo4j/import/{job_id}/"
            result = os.system(copy_cmd)
            
            if result == 0:
                copied_files.append(csv_file.name)
                print(f"Copied {csv_file.name} to Neo4j import/{job_id}/")
            else:
                return {"success": False, "message": f"Failed to copy {csv_file.name}"}
        
        return {"success": True, "files_copied": copied_files}
        
    except Exception as e:
        return {"success": False, "message": f"Error copying files: {str(e)}"}

def cleanup_neo4j_import_files(job_id: str, container_name: str = "neo4j-atomspace"):
    """Delete job-specific files from Neo4j import directory after loading"""
    try:
        cleanup_cmd = f"docker exec {container_name} rm -rf /var/lib/neo4j/import/{job_id}"
        result = os.system(cleanup_cmd)
        
        if result == 0:
            print(f"Cleaned up Neo4j import files for job {job_id}")
            return True
        else:
            print(f"Warning: Could not cleanup import files for job {job_id}")
            return False
            
    except Exception as e:
        print(f"Warning: Error cleaning up import files: {e}")
        return False

def execute_cypher_file(session, file_path, job_id):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        queries = content.split(';')
        total_operations = 0
        
        for query in queries:
            query = query.strip()
            if not query:
                continue
            
            print(f"Executing query: {query[:100]}...")
            result = session.run(query)
            records = list(result)
            if records and len(records) > 0:
                if 'total' in records[0]:
                    total_operations += records[0]['total']
                elif 'batches' in records[0]:
                    total_operations += records[0]['batches']
        
        return {"success": True, "total": total_operations}
        
    except Exception as e:
        print(f"Error executing {file_path}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/upload/create-session")
async def create_upload_session_endpoint():
    """Create a new upload session"""
    session_id = create_upload_session()
    session_dir = os.path.join(BASE_OUTPUT_DIR, "uploads", session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    return {
        "session_id": session_id,
        "expires_at": upload_sessions[session_id].expires_at.isoformat(),
        "upload_url": f"/api/upload/{session_id}/files"
    }

@app.post("/api/upload/{session_id}/files")
async def upload_files(
    session_id: str,
    files: List[UploadFile] = File(...)
):
    """Upload files to a specific session"""
    session = get_upload_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session_dir = os.path.join(BASE_OUTPUT_DIR, "uploads", session_id)
    uploaded_files = []
    
    for file in files:
        # Check for duplicate filenames
        if file.filename in session.uploaded_files:
            raise HTTPException(status_code=400, detail=f"File {file.filename} already uploaded")
        
        file_path = os.path.join(session_dir, file.filename)
        
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            session.uploaded_files.append(file.filename)
            uploaded_files.append({
                "filename": file.filename,
                "size": len(content),
                "uploaded_at": datetime.now(tz=timezone.utc).isoformat()
            })
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")
    
    return {
        "session_id": session_id,
        "uploaded_files": uploaded_files,
        "total_files": len(session.uploaded_files),
        "files_in_session": session.uploaded_files
    }

@app.get("/api/upload/{session_id}/status")
async def get_upload_status(session_id: str):
    """Get upload session status and file list"""
    session = get_upload_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session_dir = os.path.join(BASE_OUTPUT_DIR, "uploads", session_id)
    file_details = []
    
    for filename in session.uploaded_files:
        file_path = os.path.join(session_dir, filename)
        if os.path.exists(file_path):
            file_details.append({
                "filename": filename,
                "size": os.path.getsize(file_path),
                "status": "uploaded"
            })
    
    return {
        "session_id": session_id,
        "status": session.status,
        "expires_at": session.expires_at.isoformat(),
        "files": file_details,
        "total_files": len(file_details)
    }

@app.delete("/api/upload/{session_id}/files/{filename}")
async def delete_uploaded_file(session_id: str, filename: str):
    """Remove a file from upload session"""
    session = get_upload_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    if filename not in session.uploaded_files:
        raise HTTPException(status_code=404, detail="File not found in session")
    
    session_dir = os.path.join(BASE_OUTPUT_DIR, "uploads", session_id)
    file_path = os.path.join(session_dir, filename)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        session.uploaded_files.remove(filename)
        
        return {"message": f"File {filename} removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove file: {str(e)}")

@app.post("/api/load", response_model=HugeGraphLoadResponse)
async def load_data(
    files: List[UploadFile] = File(...),
    config: str = Form(...),
    schema_json: str = Form(...),
    writer_type: str = Form(...)
):
    job_id = str(uuid.uuid4())
    
    try:
        config_data = json.loads(config)
        schema_data = json.loads(schema_json)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_mapping = {}
            for file in files:
                file_path = os.path.join(tmpdir, file.filename)
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)
                file_mapping[file.filename] = file_path
            
            schema_groovy = json_to_groovy(schema_data)
            schema_path = os.path.join(tmpdir, f"schema-{job_id}.groovy")
            with open(schema_path, "w") as f:
                f.write(schema_groovy)
            
            updated_config = update_file_paths_in_config(config_data, file_mapping)
            config_path = os.path.join(tmpdir, f"struct-{job_id}.json")
            with open(config_path, "w") as f:
                json.dump(updated_config, f, indent=2)
            
            output_dir = get_job_output_dir(job_id)
            
            cmd = [
                "sh", HUGEGRAPH_LOADER_PATH,
                "-g", HUGEGRAPH_GRAPH,
                "-f", config_path,
                "-h", HUGEGRAPH_HOST,
                "-p", HUGEGRAPH_PORT,
                "--clear-all-data", "true",
                "-o", output_dir,
                "-w", writer_type,
                "--job-id", job_id
            ]
            
            if schema_path:
                cmd.extend(["-s", schema_path])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": f"HugeGraph loader failed with exit code {result.returncode}",
                        "job_id": job_id,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                )
            
            output_files = get_output_files(output_dir)
            if len(output_files) == 0:
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "No output files generated",
                        "job_id": job_id,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                )
            
            schema_json_path = os.path.join(output_dir, "schema.json")
            with open(schema_json_path, "w") as f:
                json.dump(schema_data, f, indent=2)
            
            job_metadata = {
                "job_id": job_id,
                "writer_type": writer_type,
                "created_at": str(datetime.now(tz=timezone.utc)),
                "neo4j_config": NEO4J_CONFIG if writer_type == WriterType.NEO4J else None
            }
            
            job_metadata_path = os.path.join(output_dir, "job_metadata.json")
            with open(job_metadata_path, "w") as f:
                json.dump(job_metadata, f, indent=2)
            
            metadata = load_metadata(output_dir)
            
            # Auto load to Neo4j if writer_type is neo4j
            neo4j_load_result = None
            if writer_type == "neo4j":
                neo4j_load_result = await load_data_to_neo4j(output_dir, job_id)
                
                # Save load results
                if neo4j_load_result:
                    neo4j_result_path = os.path.join(output_dir, "neo4j_load_result.json")
                    with open(neo4j_result_path, "w") as f:
                        json.dump(neo4j_load_result, f, indent=2)
            
            error_msg = await notify_annotation_service(job_id)
            if error_msg:
                selected_job_id = get_selected_job_id()
                if selected_job_id:
                    await notify_annotation_service(selected_job_id)
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)
                raise HTTPException(status_code=500, detail={"message": error_msg, "job_id": job_id})
            
            graph_info = await generate_graph_info(job_id, writer_type)
            save_graph_info(job_id, graph_info)
            save_selected_job_id(job_id)
            
            output_filenames = [os.path.basename(f) for f in output_files]
            output_filenames.extend(["schema.json", "job_metadata.json", "graph_info.json"])
            success_message = f"Graph generated successfully using {writer_type} writer"
            if neo4j_load_result and neo4j_load_result["status"] == "success":
                results = neo4j_load_result["results"]
                success_message += f" and loaded to Neo4j ({results['nodes_loaded']} nodes, {results['edges_loaded']} edges)"

            return HugeGraphLoadResponse(
                job_id=job_id,
                status="success",
                message=success_message,
                metadata=metadata,
                output_files=output_filenames,
                output_dir=output_dir,
                schema_path=schema_json_path,
                writer_type=writer_type
            )
            
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        if 'output_dir' in locals() and os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/api/select-job")
async def select_job(request: JobSelectionRequest):
    job_id = request.job_id

    if not os.path.exists(get_job_output_dir(job_id)):
        raise HTTPException(status_code=404, detail=f"Job ID {job_id} does not exist")
    
    error_msg = await notify_annotation_service(job_id)
    if error_msg:
        raise HTTPException(status_code=500, detail=f"Error connecting annotation service: {error_msg}")
    
    save_selected_job_id(job_id)
    return {"message": f"Job ID {job_id} selected successfully"}

@app.get("/api/history", response_class=JSONResponse)
async def get_history():
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    if not os.path.exists(history_path):
        return {"selected_job_id": "", "history": []}
    
    with open(history_path, 'r') as f:
        history = json.load(f)
    
    job_id = get_job_id_to_use()
    history["selected_job_id"] = job_id if job_id else ""
    return history

@app.get("/api/output/{job_id}")
async def get_output(job_id: str):
    output_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
    
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

@app.get("/api/output-file/{job_id}/{filename}")
async def get_output_file(job_id: str, filename: str):
    file_path = os.path.join(BASE_OUTPUT_DIR, job_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename} for job ID: {job_id}")
    
    return FileResponse(file_path, headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.post("/api/convert-schema", response_class=JSONResponse)
async def convert_schema(schema_json: Dict = None):
    try:
        groovy_schema = json_to_groovy(schema_json)
        return {"status": "success", "schema_groovy": groovy_schema}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error converting schema: {str(e)}")

@app.get("/api/kg-info/{job_id}", response_class=JSONResponse)
@app.get("/api/kg-info/", response_class=JSONResponse)
async def get_graph_info(job_id: str = None):
    empty_response = {
        "job_id": "",
        "node_count": 0,
        "edge_count": 0,
        "dataset_count": 0,
        "data_size": "0 B",
        "imported_on": str(datetime.now(tz=timezone.utc)),
        "top_entities": [],
        "top_connections": [],
        "frequent_relationships": [],
        "schema": {"nodes": [], "edges": []}
    }
    
    try:
        job_id = get_job_id_to_use(job_id)
        if not job_id:
            return empty_response
        
        output_dir = get_job_output_dir(job_id)
        if not os.path.exists(output_dir):
            return empty_response
        
        info_path = os.path.join(output_dir, "graph_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        job_metadata_path = os.path.join(output_dir, "job_metadata.json")
        writer_type = WriterType.METTA
        if os.path.exists(job_metadata_path):
            try:
                with open(job_metadata_path, 'r') as f:
                    job_metadata = json.load(f)
                    writer_type = WriterType(job_metadata.get("writer_type", "metta"))
            except:
                pass
        
        graph_info = await generate_graph_info(job_id, writer_type)
        save_graph_info(job_id, graph_info)
        return graph_info
    except Exception as e:
        print(f"Error in get_graph_info: {str(e)}")
        return empty_response

@app.get("/api/schema/{job_id}", response_class=JSONResponse)
@app.get("/api/schema/", response_class=JSONResponse)
async def get_annotation_schema(job_id: str = None):
    empty_response = {"job_id": "", "nodes": [], "edges": []}
    
    try:
        job_id = get_job_id_to_use(job_id)
        if not job_id:
            return empty_response
        
        output_dir = get_job_output_dir(job_id)
        schema_path = os.path.join(output_dir, "schema.json")
        annotation_path = os.path.join(output_dir, "annotation_schema.json")
        
        if not os.path.exists(output_dir) or not os.path.exists(schema_path):
            return empty_response
        
        if os.path.exists(annotation_path):
            try:
                with open(annotation_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
        
        annotation_schema = generate_annotation_schema(schema_data, job_id)
        with open(annotation_path, 'w') as f:
            json.dump(annotation_schema, f, indent=2)
        
        return annotation_schema
    except Exception as e:
        print(f"Error in get_annotation_schema: {str(e)}")
        return empty_response

@app.delete("/api/history/{job_id}")
async def delete_job_history_endpoint(job_id: str):
    updated_history, selected_job_affected = delete_job_history(job_id)
    
    job_dir = get_job_output_dir(job_id)
    dir_deleted = False
    new_selected_job = None
    
    if os.path.exists(job_dir):
        try:
            shutil.rmtree(job_dir)
            dir_deleted = True
        except Exception as e:
            print(f"Warning: Could not delete job directory {job_dir}: {e}")
    
    if selected_job_affected and updated_history["history"]:
        try:
            new_job_id = updated_history["history"][0]["job_id"]
            await select_job(JobSelectionRequest(job_id=new_job_id))
            new_selected_job = new_job_id
            updated_history["selected_job_id"] = new_job_id
        except Exception as e:
            print(f"Warning: Could not select new job: {e}")
    
    message_parts = ["Job removed from history"]
    if dir_deleted:
        message_parts.append("job directory deleted")
    if selected_job_affected:
        if new_selected_job:
            message_parts.append(f"selected job set to {new_selected_job}")
        else:
            message_parts.append("selected job was reset")
    
    updated_history["selected_job_id"] = get_job_id_to_use()
    return {
        "message": ", ".join(message_parts),
        "history": updated_history,
        "directory_deleted": dir_deleted,
        "selected_job_affected": selected_job_affected,
        "new_selected_job": new_selected_job
    }

@app.delete("/api/clear-history")
async def clear_history_endpoint():
    history = clear_history()
    return {"message": "History cleared successfully", "history": history}

@app.get("/api/neo4j/config")
async def get_neo4j_config():
    safe_config = NEO4J_CONFIG.copy()
    safe_config["password"] = "***"
    return safe_config

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.on_event("shutdown")
async def shutdown_event():
    if neo4j_driver:
        neo4j_driver.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)