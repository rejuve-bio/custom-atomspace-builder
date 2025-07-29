"""File operations utilities."""

import os
import json
import shutil
import zipfile
import io
from typing import Dict, List, Any
from pathlib import Path


def copy_files_to_temp_dir(source_dir: str, temp_dir: str) -> Dict[str, str]:
    """Copy files from source directory to temporary directory and return mapping."""
    file_mapping = {}
    
    if not os.path.exists(source_dir):
        return file_mapping
    
    for filename in os.listdir(source_dir):
        source_path = os.path.join(source_dir, filename)
        dest_path = os.path.join(temp_dir, filename)
        
        if os.path.isfile(source_path):
            shutil.copy2(source_path, dest_path)
            file_mapping[filename] = dest_path
    
    return file_mapping


def update_file_paths_in_config(config: Dict[str, Any], file_mapping: Dict[str, str]) -> Dict[str, Any]:
    """Update file paths in configuration with new mappings."""
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


def get_output_files(output_dir: str) -> List[str]:
    """Get list of output files from directory."""
    if not os.path.exists(output_dir):
        return []
    
    return [
        os.path.join(output_dir, f) 
        for f in os.listdir(output_dir) 
        if os.path.isfile(os.path.join(output_dir, f))
    ]


def create_zip_file(files: List[str]) -> io.BytesIO:
    """Create a zip file in memory from list of file paths."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for file_path in files:
            zf.write(file_path, arcname=os.path.basename(file_path))
    memory_file.seek(0)
    return memory_file


def get_directory_size(directory: str) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total


def count_files_in_directory(directory: str) -> int:
    """Count number of files in directory."""
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return 0
    try:
        return len([f for f in os.listdir(directory) 
                   if os.path.isfile(os.path.join(directory, f))])
    except Exception:
        return 0


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON from file with error handling."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json_file(file_path: str, data: Dict[str, Any]):
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def ensure_directory(directory: str):
    """Ensure directory exists, create if it doesn't."""
    os.makedirs(directory, exist_ok=True)


def cleanup_directory(directory: str, ignore_errors: bool = True):
    """Remove directory and all its contents."""
    if os.path.exists(directory):
        shutil.rmtree(directory, ignore_errors=ignore_errors)


def get_latest_directory(base_dir: str) -> str:
    """Get the most recently modified directory in base_dir."""
    if not os.path.exists(base_dir):
        return None
    
    import glob
    job_dirs = glob.glob(os.path.join(base_dir, "*"))
    if not job_dirs:
        return None
    
    job_dirs.sort(key=os.path.getmtime, reverse=True)
    return job_dirs[0]