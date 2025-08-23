"""File operations utilities."""

import csv
import os
import json
import shutil
import uuid
import zipfile
import io
from typing import Dict, List, Any, Optional
from pathlib import Path

from app.models.schemas import DataSource, FileInfo


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

def is_csv_file(filename: str) -> bool:
    """Check if file is a CSV based on extension."""
    return filename.lower().endswith('.csv')


def detect_csv_delimiter(file_path: str, sample_size: int = 1024) -> str:
    """Detect CSV delimiter by analyzing a sample of the file."""
    delimiters = [',', ';', '\t', '|', ':']
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            sample = file.read(sample_size)
        
        # Count occurrences of each delimiter
        delimiter_counts = {}
        for delimiter in delimiters:
            delimiter_counts[delimiter] = sample.count(delimiter)
        
        # Return the delimiter with the highest count (minimum 2 occurrences)
        best_delimiter = max(delimiter_counts, key=delimiter_counts.get)
        return best_delimiter if delimiter_counts[best_delimiter] >= 2 else ','
        
    except Exception as e:
        print(f"Error detecting delimiter for {file_path}: {str(e)}")
        return ','

def detect_encoding(file_path: str, sample_size: int = 8192) -> str:
    """Detect file encoding."""
    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                file.read(sample_size)
            return encoding
        except UnicodeDecodeError:
            continue
    
    # Fallback to utf-8 with error handling
    return 'utf-8'


def validate_csv_structure(file_path: str, delimiter: str = None) -> Dict[str, Any]:
    """Validate CSV file structure and return metadata."""
    if delimiter is None:
        delimiter = detect_csv_delimiter(file_path)
    
    encoding = detect_encoding(file_path)
    
    metadata = {
        "is_valid": False,
        "delimiter": delimiter,
        "encoding": encoding,
        "row_count": 0,
        "column_count": 0,
        "has_header": False,
        "errors": []
    }
    
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as file:
            csv_reader = csv.reader(file, delimiter=delimiter)
            
            rows = list(csv_reader)
            
            if not rows:
                metadata["errors"].append("File is empty")
                return metadata
            
            metadata["row_count"] = len(rows)
            metadata["column_count"] = len(rows[0]) if rows else 0
            
            # Simple heuristic to detect header
            if len(rows) >= 2:
                first_row = rows[0]
                second_row = rows[1]
                
                # Check if first row looks like headers (non-numeric strings)
                header_score = 0
                for cell in first_row:
                    if cell and not cell.replace('.', '').replace('-', '').isdigit():
                        header_score += 1
                
                metadata["has_header"] = header_score > len(first_row) * 0.5
            
            metadata["is_valid"] = True
            
    except Exception as e:
        metadata["errors"].append(str(e))
    
    return metadata

def get_file_type(filename: str) -> str:
    """Get MIME type based on file extension."""
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    
    type_mapping = {
        'csv': 'text/csv',
        'json': 'application/json',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'xlsm': 'application/vnd.ms-excel.sheet.macroEnabled.12',
        'xlsb': 'application/vnd.ms-excel.sheet.binary.macroEnabled.12',
        'txt': 'text/plain',
        'tsv': 'text/tab-separated-values'
    }
    
    return type_mapping.get(extension, 'application/octet-stream')


def create_error_datasource(filename: str, error_message: str) -> DataSource:
    """Create an error datasource for files that couldn't be processed."""
    return DataSource(
        id=f"ds_error_{uuid.uuid4().hex[:8]}",
        file=FileInfo(
            name=filename,
            size=0,
            type=get_file_type(filename)
        ),
        columns=["error"],
        sampleRow=[error_message]
    )

def clean_column_names(columns: List[str]) -> List[str]:
    """Clean and standardize column names."""
    cleaned = []
    for col in columns:
        clean_col = str(col).strip()
        
        # Handle empty or None columns
        if not clean_col or clean_col.lower() in ['none', 'null', '']:
            clean_col = f"column_{len(cleaned) + 1}"
        
        cleaned.append(clean_col)
    
    return cleaned


def clean_sample_row(row: List[str], expected_length: int) -> List[str]:
    """Clean and standardize sample row data."""
    cleaned = []
    for i, cell in enumerate(row):
        if i >= expected_length:
            break
        
        # Convert to string and strip whitespace
        clean_cell = str(cell).strip() if cell is not None else ""
        cleaned.append(clean_cell)
    
    # Pad with empty strings if row is shorter than expected
    while len(cleaned) < expected_length:
        cleaned.append("")
    
    return cleaned

def preprocess_csv_file(file_path: str, filename: str) -> Optional[DataSource]:
    """Preprocess a CSV file to extract columns and sample row."""
    try:
        # Get file stats
        file_stats = os.stat(file_path)
        file_size = file_stats.st_size
        
        # Validate and get metadata
        csv_metadata = validate_csv_structure(file_path)
        
        if not csv_metadata["is_valid"]:
            print(f"Invalid CSV file {filename}: {csv_metadata['errors']}")
            return create_error_datasource(filename, "Invalid CSV structure")
        
        delimiter = csv_metadata["delimiter"]
        encoding = csv_metadata["encoding"]
        
        with open(file_path, 'r', encoding=encoding, errors='replace') as file:
            csv_reader = csv.reader(file, delimiter=delimiter)
            
            # Get headers (first row)
            try:
                raw_columns = next(csv_reader)
                columns = clean_column_names(raw_columns)
            except StopIteration:
                return create_error_datasource(filename, "Empty file")
            
            # Get sample row (second row)
            try:
                raw_sample_row = next(csv_reader)
                sample_row = clean_sample_row(raw_sample_row, len(columns))
            except StopIteration:
                # Only header row exists, create empty sample
                sample_row = [""] * len(columns)
        
        # Generate unique ID for this data source
        ds_id = f"ds_{uuid.uuid4().hex[:8]}"
        
        return DataSource(
            id=ds_id,
            file=FileInfo(
                name=filename,
                size=file_size,
                type=get_file_type(filename)
            ),
            columns=columns,
            sampleRow=sample_row
        )
        
    except Exception as e:
        print(f"Error preprocessing CSV file {filename}: {str(e)}")
        return create_error_datasource(filename, f"Processing error: {str(e)}")
