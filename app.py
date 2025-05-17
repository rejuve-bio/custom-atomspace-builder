from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone
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

app = FastAPI(title="HugeGraph Loader API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration for HugeGraph loader
HUGEGRAPH_LOADER_PATH = "./hugegraph-loader/apache-hugegraph-loader-incubating-1.5.0/bin/hugegraph-loader.sh"
HUGEGRAPH_HOST = "localhost"
HUGEGRAPH_PORT = "8080"
HUGEGRAPH_GRAPH = "hugegraph"
BASE_OUTPUT_DIR = os.path.abspath("./output")
ANNOTATION_SERVICE_URL = "http://100.67.47.42:5800/annotation/load"
ANNOTATION_SERVICE_TIMEOUT = 300.0  # seconds
SELECTED_JOB_FILE = os.path.join(BASE_OUTPUT_DIR, "selected_job.txt")


# Schema Models
class PropertyKey(BaseModel):
    name: str
    type: str  # text, int, double, etc.
    # Optional properties
    cardinality: Optional[str] = None  # single, list, set
    # Other optional properties
    options: Optional[Dict[str, Any]] = None

class VertexLabel(BaseModel):
    name: str
    properties: List[str]
    primary_keys: Optional[List[str]] = None
    nullable_keys: Optional[List[str]] = None
    id_strategy: Optional[str] = None  # primary_key, automatic, customize_number, customize_string
    # Other optional properties
    options: Optional[Dict[str, Any]] = None

class EdgeLabel(BaseModel):
    name: str
    source_label: str
    target_label: str
    properties: Optional[List[str]] = None
    sort_keys: Optional[List[str]] = None
    # Other optional properties
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
    # schema_groovy: Optional[str] = None
    output_files: Optional[List[str]] = None
    output_dir: Optional[str] = None
    schema_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class JobSelectionRequest(BaseModel):
    job_id: str

def json_to_groovy(schema_json: Union[Dict, SchemaDefinition]) -> str:
    """
    Convert JSON schema definition to HugeGraph Groovy schema format.
    
    Args:
        schema_json: The schema definition in JSON format or as a SchemaDefinition object
        
    Returns:
        The equivalent schema in Groovy format
    """
    if isinstance(schema_json, dict):
        schema = SchemaDefinition(**schema_json)
    else:
        schema = schema_json
    
    groovy_lines = []
    
    # Process property keys
    for prop in schema.property_keys:
        line = f'schema.propertyKey("{prop.name}").as{prop.type.capitalize()}()'
        
        if prop.cardinality:
            line += f'.cardinality("{prop.cardinality}")'
        
        # Add any additional options from the options dictionary
        if prop.options:
            for opt_name, opt_value in prop.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        
        # line += '.create();'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    groovy_lines.append("")  # Empty line for readability
    
    # Process vertex labels
    for vertex in schema.vertex_labels:
        line = f'schema.vertexLabel("{vertex.name}")'
        
        # Add ID strategy if defined
        if vertex.id_strategy:
            if vertex.id_strategy == "primary_key":
                line += '.useCustomizeStringId()'  # This will be overridden by primaryKeys
            elif vertex.id_strategy == "customize_number":
                line += '.useCustomizeNumberId()'
            elif vertex.id_strategy == "customize_string":
                line += '.useCustomizeStringId()'
            elif vertex.id_strategy == "automatic":
                line += '.useAutomaticId()'
        
        # Add properties
        if vertex.properties:
            props_str = ', '.join([f'"{prop}"' for prop in vertex.properties])
            line += f'.properties({props_str})'
        
        # Add primary keys
        if vertex.primary_keys:
            keys_str = ', '.join([f'"{key}"' for key in vertex.primary_keys])
            line += f'.primaryKeys({keys_str})'
        
        # Add nullable keys
        if vertex.nullable_keys:
            keys_str = ', '.join([f'"{key}"' for key in vertex.nullable_keys])
            line += f'.nullableKeys({keys_str})'
        
        # Add any additional options
        if vertex.options:
            for opt_name, opt_value in vertex.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        
        # line += '.create();'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    groovy_lines.append("")  # Empty line for readability
    
    # Process edge labels
    for edge in schema.edge_labels:
        line = f'schema.edgeLabel("{edge.name}")'
        line += f'.sourceLabel("{edge.source_label}")'
        line += f'.targetLabel("{edge.target_label}")'
        
        # Add properties
        if edge.properties:
            props_str = ', '.join([f'"{prop}"' for prop in edge.properties])
            line += f'.properties({props_str})'
        
        # Add sort keys
        if edge.sort_keys:
            keys_str = ', '.join([f'"{key}"' for key in edge.sort_keys])
            line += f'.sortKeys({keys_str})'
        
        # Add any additional options
        if edge.options:
            for opt_name, opt_value in edge.options.items():
                if isinstance(opt_value, str):
                    line += f'.{opt_name}("{opt_value}")'
                else:
                    line += f'.{opt_name}({opt_value})'
        
        # line += '.create();'
        line += '.ifNotExist().create();'
        groovy_lines.append(line)
    
    x= '\n'.join(groovy_lines)
    print(x)
    return x


def update_file_paths_in_config(config, file_mapping):
    """
    Update file paths in the config to use the temporary file paths.
    
    Args:
        config: The configuration dictionary
        file_mapping: Dictionary mapping original filenames to temp file paths
    
    Returns:
        Updated configuration dictionary
    """
    # Create a deep copy of the config to avoid modifying the original
    updated_config = json.loads(json.dumps(config))
    
    # Function to process vertices and edges
    def update_paths(items):
        for item in items:
            if "input" in item and item["input"].get("type") == "file":
                # Extract just the filename from the path
                original_path = item["input"]["path"]
                filename = os.path.basename(original_path)
                
                # Check if this filename exists in our mapping
                if filename in file_mapping:
                    item["input"]["path"] = file_mapping[filename]
                # Otherwise, keep the original path (might be a relative path or a URL)
        
        return items
    
    # Update paths in vertices and edges
    if "vertices" in updated_config:
        updated_config["vertices"] = update_paths(updated_config["vertices"])
    
    if "edges" in updated_config:
        updated_config["edges"] = update_paths(updated_config["edges"])
    
    return updated_config


def get_job_output_dir(job_id):
    """
    Get a job-specific output directory
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Path to the output directory
    """
    output_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
    # os.makedirs(output_dir, exist_ok=True)
    return output_dir


def get_output_files(output_dir):
    """
    Get list of output files in the specified directory
    
    Args:
        output_dir: Path to output directory
        
    Returns:
        List of file paths
    """
    if not os.path.exists(output_dir):
        return []
        
    files = []
    for filename in os.listdir(output_dir):
        file_path = os.path.join(output_dir, filename)
        if os.path.isfile(file_path):
            files.append(file_path)
    
    return files


def create_zip_file(files):
    """
    Create an in-memory zip file containing the output files
    
    Args:
        files: List of file paths to include in the zip
        
    Returns:
        In-memory zip file as bytes
    """
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for file_path in files:
            # Get the relative filename
            arcname = os.path.basename(file_path)
            zf.write(file_path, arcname=arcname)
    
    memory_file.seek(0)
    return memory_file

def load_metadata(output_dir):
    metadata_file = os.path.join(output_dir, "graph_metadata.json")
    metadata = {}  # Default empty dictionary
    
    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    except FileNotFoundError:
        print(f"Metadata file not found: {metadata_file}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in metadata file: {e}")
    except Exception as e:
        print(f"Unexpected error loading metadata: {e}")
    
    return metadata

def save_graph_info(job_id: str, graph_info: dict):
    """Save graph info to a JSON file for caching"""
    output_dir = get_job_output_dir(job_id)
    info_path = os.path.join(output_dir, "graph_info.json")
    # also append it on the histroy.json which is on the BASE_OUTPUT_DIR
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    if os.path.exists(history_path):
        with open(history_path, 'r') as f:
            history = json.load(f)
    else:
        history = {"selected_job_id":"", "history": []}
    # add it in front
    history["history"] = [graph_info] + history["history"]
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    with open(info_path, 'w') as f:
        json.dump(graph_info, f, indent=2)

def get_directory_size(directory: str) -> int:
    """Calculate total size of a directory in bytes"""
    total = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # Skip if it's a symbolic link
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total

def count_files_in_directory(directory: str) -> int:
    """Count the number of files in a directory (non-recursively)"""
    if not os.path.exists(directory):
        return 0
    
    if not os.path.isdir(directory):
        return 0
    
    try:
        # List all entries in directory that are files (not directories)
        return len([
            entry for entry in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, entry))
        ])
    except Exception:
        return 0

def get_selected_job_id() -> Optional[str]:
    """Get the currently selected job ID from the file"""
    if not os.path.exists(SELECTED_JOB_FILE):
        return None
    
    try:
        with open(SELECTED_JOB_FILE, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading selected job ID: {e}")
        return None

def save_selected_job_id(job_id: str):
    """Save the selected job ID to the file"""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(SELECTED_JOB_FILE), exist_ok=True)
    
    try:
        with open(SELECTED_JOB_FILE, 'w') as f:
            f.write(job_id)
    except Exception as e:
        print(f"Error saving selected job ID: {e}")

def get_latest_job_dir(output_base_dir: str = BASE_OUTPUT_DIR) -> Optional[str]:
    """Get the most recently created job directory"""
    job_dirs = glob.glob(os.path.join(output_base_dir, "*"))
    if not job_dirs:
        return None
    # Sort by creation time (newest first)
    job_dirs.sort(key=os.path.getmtime, reverse=True)
    return job_dirs[0]

def get_job_id_to_use(job_id: Optional[str] = None) -> str:
    """
    Determine which job ID to use based on priority:
    1. Explicitly provided job_id
    2. Selected job ID from file
    3. Latest job directory
    
    Returns:
        job_id string
    Raises:
        HTTPException if no job ID can be determined
    """
    # Priority 1: Use explicitly provided job_id
    if job_id:
        if os.path.exists(get_job_output_dir(job_id)):
            return job_id
    
    # Priority 2: Use selected job ID from file
    selected_id = get_selected_job_id()
    if selected_id and os.path.exists(get_job_output_dir(selected_id)):
        return selected_id
    
    # Priority 3: Use latest job directory
    latest_dir = get_latest_job_dir()
    if latest_dir:
        return os.path.basename(latest_dir)
    
    # No valid job ID found
    raise None

async def generate_graph_info(job_id: str) -> dict:
    """Generate the graph info structure from schema and metadata"""
    output_dir = get_job_output_dir(job_id)
    dataset_count = max(count_files_in_directory(output_dir) - 2, 0)

    schema_path = os.path.join(output_dir, "schema.json")
    metadata_path = os.path.join(output_dir, "graph_metadata.json")

    with open(schema_path, 'r') as f:
        schema = json.load(f)
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Rest of the generation logic from the original endpoint...
    total_vertices = metadata.get("totalVertices", {}).get("num", 0)
    total_edges = metadata.get("totalEdges", {}).get("num", 0)

    # Calculate directory size
    dir_size = get_directory_size(output_dir)
    
    vertices_by_label = metadata.get("verticesByLabel", {})
    top_entities = [
        {"count": details["num"], "name": label}
        for label, details in vertices_by_label.items()
    ]
    top_entities.sort(key=lambda x: x["count"], reverse=True)
    
    edges_by_label = metadata.get("edgesByLabel", {})
    top_connections = [
        {"count": details["num"], "name": label}
        for label, details in edges_by_label.items()
    ]
    top_connections.sort(key=lambda x: x["count"], reverse=True)
    
    frequent_relationships = []
    edge_labels = schema.get("edge_labels", [])
    for edge in edge_labels:
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
    
    schema_nodes = []
    vertex_labels = schema.get("vertex_labels", [])
    for vertex in vertex_labels:
        schema_nodes.append({
            "data": {
                "id": vertex["name"],
                "properties": vertex.get("properties", [])
            }
        })
    
    schema_edges = []
    for edge in edge_labels:
        schema_edges.append({
            "data": {
                "source": edge["source_label"],
                "target": edge["target_label"],
                "possible_connections": [edge["name"]]
            }
        })
    
    return {
        "job_id": job_id,
        "node_count": total_vertices,
        "edge_count": total_edges,
        "dataset_count": dataset_count,
        "data_size": humanize.naturalsize(dir_size),
        # fix the timezone to UTC
        "imported_on": str(datetime.now(tz=timezone.utc)),
        "top_entities": top_entities,
        "top_connections": top_connections,
        "frequent_relationships": [
            {"count": rel["count"], "entities": rel["entities"]}
            for rel in frequent_relationships
        ],
        "schema": {
            "nodes": schema_nodes,
            "edges": schema_edges
        }
    }

def generate_annotation_schema(schema_data: dict, job_id: str) -> dict:
    """
    Convert standard schema format to annotation schema format
    """
    annotation_schema = {
        "job_id": job_id,
        "nodes": [],
        "edges": []
    }
    
    # Generate nodes from vertex labels
    for i, vertex in enumerate(schema_data.get("vertex_labels", []), 1):
        annotation_schema["nodes"].append({
            "id": vertex["name"],
            "name": vertex["name"],
            "category": "entity",  # Default category, can be customized
            "inputs": [
                {"label": prop, "name": prop, "inputType": "input"}
                for prop in vertex.get("properties", [])
            ]
        })
    
    # Generate edges from edge labels
    for i, edge in enumerate(schema_data.get("edge_labels", []), 1):
        annotation_schema["edges"].append({
            "id": str(i),
            "source": edge["source_label"],
            "target": edge["target_label"],
            "label": edge["name"]
        })
    
    return annotation_schema

async def notify_annotation_service(job_id: str) -> Dict[str, Any]:
    """
    Notify the annotation service about the new graph data.
    
    Args:
        job_id: The job ID (used as folder_id in the annotation service)
        metadata: The metadata dictionary to update with any warnings
        
    Returns:
        Updated metadata dictionary
    """
    payload = {"folder_id": job_id}
    error_msg = None
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
                
    except httpx.TimeoutException:
        error_msg = "Timeout connecting to annotation service"
        print(f"Warning: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Failed to connect to annotation service: {str(e)}"
        print(f"Warning: {error_msg}")
        return error_msg
    
    return error_msg

def clear_history():
    """Clear the history file and reset the selected job ID"""
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    # Create an empty history file
    history = {"selected_job_id": "", "history": []}
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    
    # Write the empty history
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    
    # Reset the selected job ID
    if os.path.exists(SELECTED_JOB_FILE):
        os.remove(SELECTED_JOB_FILE)
    
    return history

def delete_job_history(job_id: str):
    """
    Delete a specific job from history by job_id
    
    Args:
        job_id: ID of the job to delete
        
    Returns:
        Updated history dictionary and boolean indicating if selected job was affected
    """
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    selected_job_affected = False
    
    # If history doesn't exist, return empty history
    if not os.path.exists(history_path):
        return {"selected_job_id": "", "history": []}, selected_job_affected
    
    # Load existing history
    with open(history_path, 'r') as f:
        history = json.load(f)
    
    # Check if this is the selected job
    selected_job_id = get_selected_job_id()
    if selected_job_id == job_id:
        selected_job_affected = True
        # Don't set a new selection here - we'll do that after updating history
        
        # Clear the selected job file
        if os.path.exists(SELECTED_JOB_FILE):
            os.remove(SELECTED_JOB_FILE)
    
    # Filter out the job to delete
    original_count = len(history["history"])
    history["history"] = [item for item in history["history"] if item.get("job_id") != job_id]
    
    # Only write if something changed
    if len(history["history"]) != original_count or selected_job_affected:
        # If the selected job was affected, we'll temporarily set it to empty
        if selected_job_affected:
            history["selected_job_id"] = ""
            
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
    
    return history, selected_job_affected

@app.post("/api/load", response_model=HugeGraphLoadResponse)
async def load_data(
    files: List[UploadFile] = File(...),
    config: str = Form(...),
    schema_json: Optional[str] = Form(None),
):
    """
    API endpoint to load data into HugeGraph.
    
    - files: Multiple data files to be loaded
    - config: JSON configuration similar to struct.json
    - schema_json: Optional schema in JSON format that will be converted to Groovy
    """
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Parse the config
        config_data = json.loads(config)
        
        # Create a temporary directory for this job
        with tempfile.TemporaryDirectory() as tmpdir:
            # Dictionary to map original filenames to their paths in the temp directory
            file_mapping = {}
            
            # Save all uploaded files to temp directory
            for file in files:
                file_path = os.path.join(tmpdir, file.filename)
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)
                file_mapping[file.filename] = file_path
            
            # Convert JSON schema to Groovy if provided
            schema_path = None
            schema_groovy = None
            if schema_json:
                schema_data = json.loads(schema_json)
                schema_groovy = json_to_groovy(schema_data)
                schema_path = os.path.join(tmpdir, f"schema-{job_id}.groovy")
                with open(schema_path, "w") as f:
                    f.write(schema_groovy)
            else:
                raise HTTPException(status_code=400, detail="Schema JSON is required")
            
            # Update the paths in the config to point to the temp files
            updated_config = update_file_paths_in_config(config_data, file_mapping)
            
            # Save the updated config to a file
            config_path = os.path.join(tmpdir, f"struct-{job_id}.json")
            with open(config_path, "w") as f:
                json.dump(updated_config, f, indent=2)
            
            # Get job-specific output directory
            output_dir = get_job_output_dir(job_id)
            
            # Build the HugeGraph loader command
            cmd = [
                "sh", HUGEGRAPH_LOADER_PATH,
                "-g", HUGEGRAPH_GRAPH,
                "-f", config_path,
                "-h", HUGEGRAPH_HOST,
                "-p", HUGEGRAPH_PORT,
                "--clear-all-data", "true",
                "-o", output_dir  # Specify output directory
            ]
            
            if schema_path:
                cmd.extend(["-s", schema_path])
            
            # Run the command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Get output files
            output_files = get_output_files(output_dir)
            output_filenames = [os.path.basename(f) for f in output_files]
            metadata = load_metadata(output_dir)

            if result.returncode != 0:
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
                
            if len(output_files) == 0:
                # delete the directory
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
            
            # save the schema json to the output directory
            schema_json_path = os.path.join(output_dir, f"schema.json")
            with open(schema_json_path, "w") as f:
                json.dump(schema_data, f, indent=2)
            output_filenames.append(os.path.basename(schema_json_path))

            # Notify the annotation service
            error_msg = await notify_annotation_service(job_id)
            if error_msg:
                select_job_id = get_selected_job_id()
                notify_annotation_service(job_id)
                # delete the directory
                shutil.rmtree(output_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": error_msg,
                        "job_id": job_id
                    }
                )
            
            # Generate and save graph info
            graph_info = await generate_graph_info(job_id) 
            save_graph_info(job_id, graph_info)
            output_filenames.append("graph_info.json")
            save_selected_job_id(job_id)

            return HugeGraphLoadResponse(
                job_id=job_id,
                status="success",
                message="Graph generated successfully",
                metadata=metadata,
                output_files=output_filenames,
                output_dir=output_dir,
                schema_path=schema_json_path
            )
            
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/api/select-job")
async def select_job(request: JobSelectionRequest):
    """
    Select a job ID for future requests.

    Args:
        request: JSON body with job_id

    Returns:
        Confirmation message
    """
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
    """
    Retrieve the history of loaded jobs from history.json in the BASE_outputdir.
    
    Returns:
        List of job history items
    """
    history_path = os.path.join(BASE_OUTPUT_DIR, "history.json")
    if not os.path.exists(history_path):
        # Return empty history rather than 404
        return {"selected_job_id": "", "history": []}
    
    with open(history_path, 'r') as f:
        history = json.load(f)
    
    job_id = get_job_id_to_use()
    history["selected_job_id"] = job_id if job_id else ""
    
    return history

@app.get("/api/output/{job_id}")
async def get_output(job_id: str):
    """
    Retrieve output files for a specific job
    
    Args:
        job_id: The job ID to retrieve output files for
        
    Returns:
        Zip file containing all output files
    """
    output_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
    
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail=f"No output files found for job ID: {job_id}")
    
    files = get_output_files(output_dir)
    
    if not files:
        raise HTTPException(status_code=404, detail=f"No output files found for job ID: {job_id}")
    
    # Create a zip file with all output files
    zip_bytes = create_zip_file(files)
    
    return StreamingResponse(
        zip_bytes, 
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=output-{job_id}.zip"}
    )


@app.get("/api/output-file/{job_id}/{filename}")
async def get_output_file(job_id: str, filename: str):
    """
    Retrieve a specific output file for a job
    
    Args:
        job_id: The job ID
        filename: The filename to retrieve
        
    Returns:
        The requested file
    """
    file_path = os.path.join(BASE_OUTPUT_DIR, job_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename} for job ID: {job_id}")
    
    return FileResponse(
        file_path,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/convert-schema", response_class=JSONResponse)
async def convert_schema(schema_json: Dict = None):
    """
    Convert JSON schema to Groovy format without loading data.
    
    Args:
        schema_json: The schema definition in JSON format
        
    Returns:
        The equivalent schema in Groovy format
    """
    try:
        groovy_schema = json_to_groovy(schema_json)
        return {
            "status": "success",
            "schema_groovy": groovy_schema
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error converting schema: {str(e)}")

@app.get("/api/kg-info/{job_id}", response_class=JSONResponse)
@app.get("/api/kg-info/", response_class=JSONResponse)
async def get_graph_info(job_id: str = None):
    """
    Get comprehensive graph information:
    - If job_id provided: uses that specific job's data
    - If no job_id: uses selected or most recently created job directory
    - If no jobs exist: returns empty graph structure
    """
    # Get the job ID to use
    job_id = get_job_id_to_use(job_id)
    
    # Return empty structure if no job ID available
    if not job_id:
        return {
            "job_id": "",
            "node_count": 0,
            "edge_count": 0,
            "dataset_count": 0,
            "data_size": "0 B",
            "imported_on": str(datetime.now(tz=timezone.utc)),
            "top_entities": [],
            "top_connections": [],
            "frequent_relationships": [],
            "schema": {
                "nodes": [],
                "edges": []
            }
        }
    
    output_dir = get_job_output_dir(job_id)
    info_path = os.path.join(output_dir, "graph_info.json")
    
    if not os.path.exists(output_dir):
        raise HTTPException(
            status_code=404,
            detail=f"Job directory not found: {job_id}"
        )
    
    # If cached version exists, return it
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cached graph info: {e}")
    
    # Otherwise generate fresh and cache it
    try:
        graph_info = await generate_graph_info(job_id)
        save_graph_info(job_id, graph_info)
        return graph_info
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating graph info: {str(e)}"
        )

@app.get("/api/schema/{job_id}", response_class=JSONResponse)
@app.get("/api/schema/", response_class=JSONResponse)
async def get_annotation_schema(job_id: str = None):
    """
    Get annotation schema, using either provided job_id, selected job, or latest job.
    Returns empty schema structure if no jobs exist.
    """
    # Get the job ID to use
    job_id = get_job_id_to_use(job_id)
    
    # Return empty structure if no job ID available
    if not job_id:
        return {
            "job_id": "",
            "nodes": [],
            "edges": []
        }
    
    output_dir = get_job_output_dir(job_id)
    schema_path = os.path.join(output_dir, "schema.json")
    annotation_path = os.path.join(output_dir, "annotation_schema.json")
    
    # Return cached version if exists
    if os.path.exists(annotation_path):
        try:
            with open(annotation_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cached annotation schema: {e}")
    
    # Generate fresh if no cache exists
    try:
        if not os.path.exists(schema_path):
            raise HTTPException(
                status_code=404,
                detail=f"Schema file not found for job {job_id}"
            )
            
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
        
        annotation_schema = generate_annotation_schema(schema_data, job_id)
        
        # Save for future requests
        with open(annotation_path, 'w') as f:
            json.dump(annotation_schema, f, indent=2)
        
        return annotation_schema
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating annotation schema: {str(e)}"
        )

@app.delete("/api/history/{job_id}")
async def delete_job_history_endpoint(job_id: str):
    """
    Delete a specific job from history by job_id
    
    Args:
        job_id: ID of the job to delete
        
    Returns:
        Confirmation message and updated history
    """
    # Delete the job from history
    updated_history, selected_job_affected = delete_job_history(job_id)
    
    # Try to delete the job directory if it exists
    job_dir = get_job_output_dir(job_id)
    dir_deleted = False
    new_selected_job = None
    
    if os.path.exists(job_dir):
        try:
            shutil.rmtree(job_dir)
            dir_deleted = True
        except Exception as e:
            print(f"Warning: Could not delete job directory {job_dir}: {e}")
    
    # If the selected job was affected and we have jobs in history, select the first job
    if selected_job_affected and updated_history["history"]:
        try:
            # Get the first job ID from history
            new_job_id = updated_history["history"][0]["job_id"]
            
            # Use the existing select_job functionality to set the new job
            await select_job(JobSelectionRequest(job_id=new_job_id))
            new_selected_job = new_job_id
            
            # Update the history object with the new selection
            updated_history["selected_job_id"] = new_job_id
        except Exception as e:
            print(f"Warning: Could not select new job: {e}")
    
    # Generate appropriate message
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

@app.post("/api/clear-history")
async def clear_history_endpoint():
    """
    Clear the job history and reset the selected job ID
    
    Returns:
        Confirmation message and empty history
    """
    history = clear_history()
    return {
        "message": "History cleared successfully",
        "history": history
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)