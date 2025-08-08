"""Neo4j database operations service - Fixed version with correct path mapping."""

from http.client import HTTPException
import os
import shutil
from pathlib import Path
from typing import Dict, Any
from ..core.database import neo4j_manager
from ..models.schemas import Neo4jLoadResult


class Neo4jService:
    """Service for Neo4j database operations."""
    
    def __init__(self):
        # Use Neo4j's import directory which is mounted as a shared volume
        self.shared_output_path = "/shared/output"
        # This is the path Neo4j sees internally when using file:/// URLs
        self.neo4j_import_path = "/var/lib/neo4j/import"
    
    async def load_data_to_neo4j(self, output_dir: str, job_id: str) -> Neo4jLoadResult:
        """Load generated CSV files to Neo4j using shared volume."""
        if not neo4j_manager.is_connected():
            return Neo4jLoadResult(
                status="error", 
                message="Neo4j driver not initialized"
            )
        
        try:
            # Step 1: Copy CSV files to shared volume
            copy_result = self._copy_files_to_shared_volume(output_dir, job_id)
            if not copy_result["success"]:
                return Neo4jLoadResult(
                    status="error", 
                    message=copy_result["message"]
                )
            
            print(f"Successfully copied {len(copy_result['files_copied'])} files to shared volume")
            
            # Step 2: Execute Cypher files with path correction
            with neo4j_manager.get_session() as session:
                # Find all cypher files
                node_files = sorted(Path(output_dir).glob("nodes_*.cypher"))
                edge_files = sorted(Path(output_dir).glob("edges_*.cypher"))
                
                print(f"Found Cypher files - Nodes: {len(node_files)}, Edges: {len(edge_files)}")
                
                results = {"nodes_loaded": 0, "edges_loaded": 0, "files_processed": []}
                
                # Process node files first
                for file_path in node_files:
                    print(f"Processing node file: {file_path.name}")
                    result = self._execute_cypher_file(session, file_path, job_id)
                    if result["success"]:
                        results["nodes_loaded"] += result.get("total", 0)
                        results["files_processed"].append(str(file_path.name))
                    else:
                        print(f"Failed to process {file_path.name}: {result.get('error', 'Unknown error')}")
                
                # Process edge files second
                for file_path in edge_files:
                    print(f"Processing edge file: {file_path.name}")
                    result = self._execute_cypher_file(session, file_path, job_id)
                    if result["success"]:
                        results["edges_loaded"] += result.get("total", 0)
                        results["files_processed"].append(str(file_path.name))
                    else:
                        print(f"Failed to process {file_path.name}: {result.get('error', 'Unknown error')}")
                
                # Step 3: Cleanup shared files after successful loading
                self._cleanup_shared_files(job_id)
                
                return Neo4jLoadResult(
                    status="success",
                    job_id=job_id,
                    tenant_id=job_id,
                    results=results
                )
                
        except Exception as e:
            print(f"Error in load_data_to_neo4j: {str(e)}")
            # Try to cleanup even if loading failed
            self._cleanup_shared_files(job_id)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load data to Neo4j: {str(e)}"
            )
    
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
    
    def _copy_files_to_shared_volume(self, output_dir: str, job_id: str) -> Dict[str, Any]:
        """Copy CSV files to shared volume accessible by both containers."""
        try:
            csv_files = list(Path(output_dir).glob("*.csv"))
            if not csv_files:
                return {"success": False, "message": "No CSV files found"}
            
            # Create job-specific directory in shared volume
            shared_job_dir = os.path.join(self.shared_output_path, job_id)
            os.makedirs(shared_job_dir, exist_ok=True)
            
            copied_files = []
            for csv_file in csv_files:
                # Copy file to shared volume
                dest_path = os.path.join(shared_job_dir, csv_file.name)
                shutil.copy2(csv_file, dest_path)
                copied_files.append(csv_file.name)
                print(f"Copied {csv_file.name} to shared volume: {dest_path}")
            
            return {"success": True, "files_copied": copied_files}
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to copy CSV files to job-specific directory: {csv_copy_result['message']}"
            )
    
    def _cleanup_shared_files(self, job_id: str) -> bool:
        """Delete job-specific files from shared volume after loading."""
        try:
            shared_job_dir = os.path.join(self.shared_output_path, job_id)
            if os.path.exists(shared_job_dir):
                shutil.rmtree(shared_job_dir)
                print(f"Cleaned up shared files for job {job_id}")
                return True
            return True
                
        except Exception as e:
            print(f"Warning: Error cleaning up shared files: {e}")
            return False
    
    def _execute_cypher_file(self, session, file_path: Path, job_id: str) -> Dict[str, Any]:
        """Execute a Cypher file with corrected paths for Neo4j container."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            print(f"Executing Cypher file: {file_path.name}")
            # print(f"Content preview (with fixed paths): {content[:200]}...")
            
            # Split and execute queries
            queries = [q.strip() for q in content.split(';') if q.strip()]
            total_operations = 0
            
            for i, query in enumerate(queries):
                if not query:
                    continue
                
                try:
                    # print(f"Executing query {i+1}/{len(queries)}")
                    result = session.run(query)
                    summary = result.consume()
                    
                    # Count operations from summary
                    if hasattr(summary, 'counters'):
                        counters = summary.counters
                        nodes_created = counters.nodes_created
                        relationships_created = counters.relationships_created
                        properties_set = counters.properties_set
                        
                        total_operations += (nodes_created + relationships_created + properties_set)
                        print(f"Query {i+1} completed: {nodes_created} nodes, {relationships_created} relationships, {properties_set} properties")
                    else:
                        total_operations += 1
                        print(f"Query {i+1} completed")
                        
                except Exception as query_error:
                    print(f"Error in query {i+1}: {str(query_error)}")
                    print(f"Query content: {query[:500]}...")
                    return {"success": False, "error": f"Query {i+1} failed: {str(query_error)}"}
            
            print(f"Successfully executed {len(queries)} queries with {total_operations} total operations")
            return {"success": True, "total": total_operations}
            
        except Exception as e:
            print(f"Error executing {file_path}: {e}")
            # return {"success": False, "error": str(e)}
            raise e


# Global service instance
neo4j_service = Neo4jService()