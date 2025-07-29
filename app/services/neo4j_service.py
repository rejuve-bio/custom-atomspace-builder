"""Neo4j database operations service."""

import os
import json
from pathlib import Path
from typing import Dict, Any
from ..core.database import neo4j_manager
from ..models.schemas import Neo4jLoadResult
from ..config import settings


class Neo4jService:
    """Service for Neo4j database operations."""
    
    def __init__(self):
        self.container_name = "neo4j-atomspace"  # Default container name
    
    async def load_data_to_neo4j(self, output_dir: str, job_id: str) -> Neo4jLoadResult:
        """Load generated CSV files to Neo4j using Cypher scripts."""
        if not neo4j_manager.is_connected():
            return Neo4jLoadResult(
                status="error", 
                message="Neo4j driver not initialized"
            )
        
        try:
            # Step 1: Copy CSV files to job-specific directory
            csv_copy_result = self._copy_csv_files_to_neo4j(output_dir, job_id)
            if not csv_copy_result["success"]:
                return Neo4jLoadResult(
                    status="error", 
                    message=csv_copy_result["message"]
                )
            
            # Step 2: Execute Cypher files
            with neo4j_manager.get_session() as session:
                # Find all cypher files
                node_files = sorted(Path(output_dir).glob("nodes_*.cypher"))
                edge_files = sorted(Path(output_dir).glob("edges_*.cypher"))
                
                results = {"nodes_loaded": 0, "edges_loaded": 0, "files_processed": []}
                
                # Process node files first
                for file_path in node_files:
                    result = self._execute_cypher_file(session, file_path, job_id)
                    if result["success"]:
                        results["nodes_loaded"] += result.get("total", 0)
                        results["files_processed"].append(str(file_path.name))
                
                # Process edge files second
                for file_path in edge_files:
                    result = self._execute_cypher_file(session, file_path, job_id)
                    if result["success"]:
                        results["edges_loaded"] += result.get("total", 0)
                        results["files_processed"].append(str(file_path.name))
                
                # Step 3: Cleanup import files after successful loading
                self._cleanup_neo4j_import_files(job_id)
                
                return Neo4jLoadResult(
                    status="success",
                    job_id=job_id,
                    tenant_id=job_id,
                    results=results
                )
                
        except Exception as e:
            # Try to cleanup even if loading failed
            self._cleanup_neo4j_import_files(job_id)
            return Neo4jLoadResult(status="error", message=str(e))
    
    def delete_subgraph(self, job_id: str) -> bool:
        """Delete all nodes and relationships in Neo4j with tenant_id == job_id."""
        if not neo4j_manager.is_connected():
            print("Neo4j driver is not initialized. Skipping deletion.")
            return False

        try:
            delete_query = """
            MATCH (n) 
            WHERE n.tenant_id = $tenant_id 
            DETACH DELETE n
            """
            neo4j_manager.execute_query(delete_query, {"tenant_id": job_id})
            print(f"Deleted Neo4j subgraph for tenant_id/job_id: {job_id}")
            return True
        except Exception as e:
            print(f"Error deleting Neo4j subgraph for job_id {job_id}: {str(e)}")
            return False
    
    def _copy_csv_files_to_neo4j(self, output_dir: str, job_id: str) -> Dict[str, Any]:
        """Copy CSV files to Neo4j container import/job_id directory."""
        try:
            csv_files = list(Path(output_dir).glob("*.csv"))
            if not csv_files:
                return {"success": False, "message": "No CSV files found"}
            
            # Create job-specific directory in Neo4j import
            mkdir_cmd = f"docker exec {self.container_name} mkdir -p /var/lib/neo4j/import/{job_id}"
            os.system(mkdir_cmd)
            
            copied_files = []
            for csv_file in csv_files:
                # Copy file to job-specific directory
                copy_cmd = f"docker cp {csv_file} {self.container_name}:/var/lib/neo4j/import/{job_id}/"
                result = os.system(copy_cmd)
                
                if result == 0:
                    copied_files.append(csv_file.name)
                    print(f"Copied {csv_file.name} to Neo4j import/{job_id}/")
                else:
                    return {"success": False, "message": f"Failed to copy {csv_file.name}"}
            
            return {"success": True, "files_copied": copied_files}
            
        except Exception as e:
            return {"success": False, "message": f"Error copying files: {str(e)}"}
    
    def _cleanup_neo4j_import_files(self, job_id: str) -> bool:
        """Delete job-specific files from Neo4j import directory after loading."""
        try:
            cleanup_cmd = f"docker exec {self.container_name} rm -rf /var/lib/neo4j/import/{job_id}"
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
    
    def _execute_cypher_file(self, session, file_path: Path, job_id: str) -> Dict[str, Any]:
        """Execute a Cypher file and return results."""
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


# Global service instance
neo4j_service = Neo4jService()