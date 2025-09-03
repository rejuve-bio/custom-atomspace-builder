"""Neo4j database operations service - Enhanced with driver initialization handling."""

from http.client import HTTPException
import os
import shutil
from pathlib import Path
from typing import Dict, Any
from ..core.database import neo4j_manager
from ..models.schemas import Neo4jLoadResult
import logging

logger = logging.getLogger(__name__)


class Neo4jService:
    """Service for Neo4j database operations."""
    
    def __init__(self):
        # Use Neo4j's import directory which is mounted as a shared volume
        self.shared_output_path = "/shared/output"
        # This is the path Neo4j sees internally when using file:/// URLs
        self.neo4j_import_path = "/var/lib/neo4j/import"
    
    def _ensure_neo4j_connection(self, wait_timeout: float = 30.0) -> bool:
        """Ensure Neo4j connection is available, initialize if needed."""
        if neo4j_manager.is_connected():
            return True
        
        logger.info("Neo4j driver not initialized, attempting to establish connection...")
        
        # Try to wait for existing background initialization
        if neo4j_manager.wait_for_connection(timeout=wait_timeout):
            logger.info("Neo4j connection established via background initialization")
            return True
        
        # If still not connected, try manual initialization
        logger.info("Attempting manual Neo4j driver initialization...")
        if neo4j_manager.initialize_driver():
            logger.info("Neo4j driver manually initialized successfully")
            return True
        
        logger.error("Failed to establish Neo4j connection")
        return False
    
    async def load_data_to_neo4j(self, output_dir: str, job_id: str) -> Neo4jLoadResult:
        """Load generated CSV files to Neo4j using shared volume."""
        # Ensure Neo4j connection is available
        if not self._ensure_neo4j_connection(wait_timeout=60.0):
            return Neo4jLoadResult(
                status="error", 
                message="Neo4j driver could not be initialized. Database may still be starting up."
            )
        
        try:
            # Step 1: Copy CSV files to shared volume
            copy_result = self._copy_files_to_shared_volume(output_dir, job_id)
            if not copy_result["success"]:
                return Neo4jLoadResult(
                    status="error", 
                    message=copy_result["message"]
                )
            
            logger.info(f"Successfully copied {len(copy_result['files_copied'])} files to shared volume")
            
            # Step 2: Execute Cypher files with path correction
            try:
                with neo4j_manager.get_session() as session:
                    # Find all cypher files
                    node_files = sorted(Path(output_dir).glob("nodes_*.cypher"))
                    edge_files = sorted(Path(output_dir).glob("edges_*.cypher"))
                    
                    logger.info(f"Found Cypher files - Nodes: {len(node_files)}, Edges: {len(edge_files)}")
                    
                    results = {"nodes_loaded": 0, "edges_loaded": 0, "files_processed": []}
                    
                    # Process node files first
                    for file_path in node_files:
                        logger.info(f"Processing node file: {file_path.name}")
                        result = self._execute_cypher_file(session, file_path, job_id)
                        if result["success"]:
                            results["nodes_loaded"] += result.get("total", 0)
                            results["files_processed"].append(str(file_path.name))
                        else:
                            logger.error(f"Failed to process {file_path.name}: {result.get('error', 'Unknown error')}")
                    
                    # Process edge files second
                    for file_path in edge_files:
                        logger.info(f"Processing edge file: {file_path.name}")
                        result = self._execute_cypher_file(session, file_path, job_id)
                        if result["success"]:
                            results["edges_loaded"] += result.get("total", 0)
                            results["files_processed"].append(str(file_path.name))
                        else:
                            logger.error(f"Failed to process {file_path.name}: {result.get('error', 'Unknown error')}")
                    
                    # Step 3: Cleanup shared files after successful loading
                    self._cleanup_shared_files(job_id)
                    
                    return Neo4jLoadResult(
                        status="success",
                        job_id=job_id,
                        tenant_id=job_id,
                        results=results
                    )
            
            except RuntimeError as e:
                if "not initialized" in str(e):
                    logger.error("Neo4j connection lost during operation")
                    return Neo4jLoadResult(
                        status="error", 
                        message="Neo4j connection was lost during operation. Please try again."
                    )
                raise
                
        except Exception as e:
            logger.error(f"Error in load_data_to_neo4j: {str(e)}")
            # Try to cleanup even if loading failed
            self._cleanup_shared_files(job_id)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load data to Neo4j: {str(e)}"
            )
    
    def delete_subgraph(self, job_id: str, retry_on_failure: bool = True) -> bool:
        """Delete all nodes and relationships in Neo4j with tenant_id == job_id."""
        # Ensure Neo4j connection is available
        if not self._ensure_neo4j_connection(wait_timeout=30.0):
            logger.warning("Neo4j driver could not be initialized. Skipping deletion.")
            return False

        try:
            delete_query = """
            MATCH (n) 
            WHERE n.tenant_id = $tenant_id 
            DETACH DELETE n
            """
            
            # Use the enhanced execute_query with connection waiting
            neo4j_manager.execute_query(
                delete_query, 
                {"tenant_id": job_id},
                wait_for_connection=True
            )
            
            logger.info(f"Deleted Neo4j subgraph for tenant_id/job_id: {job_id}")
            return True
            
        except RuntimeError as e:
            if "not initialized" in str(e) or "not available" in str(e):
                logger.warning(f"Neo4j connection issue during deletion for job_id {job_id}: {str(e)}")
                if retry_on_failure:
                    logger.info("Retrying deletion after connection issue...")
                    return self.delete_subgraph(job_id, retry_on_failure=False)
            else:
                logger.error(f"Error deleting Neo4j subgraph for job_id {job_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting Neo4j subgraph for job_id {job_id}: {str(e)}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status for monitoring."""
        return neo4j_manager.health_check()
    
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
                logger.debug(f"Copied {csv_file.name} to shared volume: {dest_path}")
            
            return {"success": True, "files_copied": copied_files}
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to copy CSV files to job-specific directory: {e}"
            )
    
    def _cleanup_shared_files(self, job_id: str) -> bool:
        """Delete job-specific files from shared volume after loading."""
        try:
            shared_job_dir = os.path.join(self.shared_output_path, job_id)
            if os.path.exists(shared_job_dir):
                shutil.rmtree(shared_job_dir)
                logger.info(f"Cleaned up shared files for job {job_id}")
                return True
            return True
                
        except Exception as e:
            logger.warning(f"Error cleaning up shared files: {e}")
            return False
    
    def _execute_cypher_file(self, session, file_path: Path, job_id: str) -> Dict[str, Any]:
        """Execute a Cypher file with corrected paths for Neo4j container."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            logger.info(f"Executing Cypher file: {file_path.name}")
            
            # Split and execute queries
            queries = [q.strip() for q in content.split(';') if q.strip()]
            total_operations = 0
            
            for i, query in enumerate(queries):
                if not query:
                    continue
                
                try:
                    result = session.run(query)
                    summary = result.consume()
                    
                    # Count operations from summary
                    if hasattr(summary, 'counters'):
                        counters = summary.counters
                        nodes_created = counters.nodes_created
                        relationships_created = counters.relationships_created
                        properties_set = counters.properties_set
                        
                        total_operations += (nodes_created + relationships_created + properties_set)
                        logger.debug(f"Query {i+1} completed: {nodes_created} nodes, {relationships_created} relationships, {properties_set} properties")
                    else:
                        total_operations += 1
                        logger.debug(f"Query {i+1} completed")
                        
                except Exception as query_error:
                    logger.error(f"Error in query {i+1}: {str(query_error)}")
                    logger.error(f"Query content: {query[:500]}...")
                    return {"success": False, "error": f"Query {i+1} failed: {str(query_error)}"}
            
            logger.info(f"Successfully executed {len(queries)} queries with {total_operations} total operations")
            return {"success": True, "total": total_operations}
            
        except Exception as e:
            logger.error(f"Error executing {file_path}: {e}")
            raise e


neo4j_service = Neo4jService()