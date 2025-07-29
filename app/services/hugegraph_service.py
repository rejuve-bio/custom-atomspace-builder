"""HugeGraph loading and processing service."""

import json
import os
import subprocess
import tempfile
import uuid
from typing import Dict, Any, Tuple
from ..models.schemas import SchemaDefinition, HugeGraphLoadResponse
from ..models.enums import WriterType
from ..config import settings
from ..utils.schema_converter import json_to_groovy
from ..utils.file_utils import copy_files_to_temp_dir, update_file_paths_in_config


class HugeGraphService:
    """Service for HugeGraph operations."""
    
    def __init__(self):
        self.base_output_dir = settings.base_output_dir
    
    async def process_data(
        self,
        files_dir: str,
        config_data: Dict[str, Any],
        schema_data: Dict[str, Any],
        writer_type: str = WriterType.METTA
    ) -> HugeGraphLoadResponse:
        """Process data using HugeGraph loader."""
        job_id = str(uuid.uuid4())
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Copy files and prepare paths
                file_mapping = copy_files_to_temp_dir(files_dir, tmpdir)
                
                # Generate schema and config files
                schema_path = self._create_schema_file(schema_data, job_id, tmpdir)
                config_path = self._create_config_file(config_data, file_mapping, job_id, tmpdir)
                
                # Prepare output directory
                output_dir = self._get_job_output_dir(job_id)
                
                # Run HugeGraph loader
                result = self._run_hugegraph_loader(
                    config_path, schema_path, output_dir, job_id, writer_type
                )
                
                if result.returncode != 0:
                    self._cleanup_failed_job(output_dir)
                    raise Exception(f"HugeGraph loader failed: {result.stderr}")
                
                # Save additional metadata
                self._save_job_metadata(output_dir, job_id, writer_type, schema_data)
                
                output_files = self._get_output_files(output_dir)
                if not output_files:
                    self._cleanup_failed_job(output_dir)
                    raise Exception("No output files generated")
                
                return HugeGraphLoadResponse(
                    job_id=job_id,
                    status="success",
                    message=f"Graph generated successfully using {writer_type} writer",
                    output_files=[os.path.basename(f) for f in output_files],
                    output_dir=output_dir,
                    schema_path=os.path.join(output_dir, "schema.json"),
                    writer_type=writer_type
                )
                
        except Exception as e:
            # Cleanup on failure
            output_dir = self._get_job_output_dir(job_id)
            self._cleanup_failed_job(output_dir)
            raise e
    
    def _create_schema_file(self, schema_data: Dict[str, Any], job_id: str, tmpdir: str) -> str:
        """Create Groovy schema file."""
        schema_groovy = json_to_groovy(schema_data)
        schema_path = os.path.join(tmpdir, f"schema-{job_id}.groovy")
        
        with open(schema_path, "w") as f:
            f.write(schema_groovy)
        
        return schema_path
    
    def _create_config_file(
        self, 
        config_data: Dict[str, Any], 
        file_mapping: Dict[str, str], 
        job_id: str, 
        tmpdir: str
    ) -> str:
        """Create updated config file with correct file paths."""
        updated_config = update_file_paths_in_config(config_data, file_mapping)
        config_path = os.path.join(tmpdir, f"struct-{job_id}.json")
        
        with open(config_path, "w") as f:
            json.dump(updated_config, f, indent=2)
        
        return config_path
    
    def _run_hugegraph_loader(
        self, 
        config_path: str, 
        schema_path: str, 
        output_dir: str, 
        job_id: str, 
        writer_type: str
    ) -> subprocess.CompletedProcess:
        """Execute HugeGraph loader command."""
        cmd = [
            "sh", settings.hugegraph_loader_path,
            "-g", settings.hugegraph_graph,
            "-f", config_path,
            "-h", settings.hugegraph_host,
            "-p", settings.hugegraph_port,
            "--clear-all-data", "true",
            "-o", output_dir,
            "-w", writer_type,
            "--job-id", job_id
        ]
        
        if schema_path:
            cmd.extend(["-s", schema_path])
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def _save_job_metadata(
        self, 
        output_dir: str, 
        job_id: str, 
        writer_type: str, 
        schema_data: Dict[str, Any]
    ):
        """Save job metadata and schema to output directory."""
        # Save schema JSON
        schema_json_path = os.path.join(output_dir, "schema.json")
        with open(schema_json_path, "w") as f:
            json.dump(schema_data, f, indent=2)
        
        # Save job metadata
        from datetime import datetime, timezone
        job_metadata = {
            "job_id": job_id,
            "writer_type": writer_type,
            "created_at": str(datetime.now(tz=timezone.utc)),
            "neo4j_config": settings.neo4j_config if writer_type == WriterType.NEO4J else None
        }
        
        job_metadata_path = os.path.join(output_dir, "job_metadata.json")
        with open(job_metadata_path, "w") as f:
            json.dump(job_metadata, f, indent=2)
    
    def _get_job_output_dir(self, job_id: str) -> str:
        """Get output directory path for a job."""
        return os.path.join(self.base_output_dir, job_id)
    
    def _get_output_files(self, output_dir: str) -> list:
        """Get list of output files from job directory."""
        if not os.path.exists(output_dir):
            return []
        
        return [
            os.path.join(output_dir, f) 
            for f in os.listdir(output_dir) 
            if os.path.isfile(os.path.join(output_dir, f))
        ]
    
    def _cleanup_failed_job(self, output_dir: str):
        """Clean up output directory for failed jobs."""
        import shutil
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


# Global service instance
hugegraph_service = HugeGraphService()