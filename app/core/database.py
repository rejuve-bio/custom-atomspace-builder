"""Database connection management for Neo4j."""

from neo4j import GraphDatabase
from typing import Optional
from ..config import settings


class Neo4jManager:
    """Manages Neo4j database connections."""
    
    def __init__(self):
        self.driver: Optional[GraphDatabase] = None
        self._initialized = False
    
    def initialize_driver(self) -> bool:
        """Initialize the Neo4j driver with connection pooling."""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=settings.neo4j_auth,
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_timeout=10,
                encrypted=False
            )
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1").consume()
            
            print("Neo4j driver initialized successfully")
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"Failed to initialize Neo4j driver: {e}")
            print("Neo4j features will be disabled until connection is restored")
            self._initialized = False
            return False
    
    def close_driver(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            print("Neo4j driver closed")
            self._initialized = False
    
    def is_connected(self) -> bool:
        """Check if Neo4j driver is properly initialized."""
        return self._initialized and self.driver is not None
    
    def get_session(self):
        """Get a Neo4j session. Use in context manager."""
        if not self.is_connected():
            raise RuntimeError("Neo4j driver is not initialized")
        
        return self.driver.session(database=settings.neo4j_config["database"])
    
    def execute_query(self, query: str, parameters: dict = None):
        """Execute a single query and return results."""
        if not self.is_connected():
            raise RuntimeError("Neo4j driver is not initialized")
        
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return list(result)
    
    def execute_transaction(self, tx_function, *args, **kwargs):
        """Execute a transaction function."""
        if not self.is_connected():
            raise RuntimeError("Neo4j driver is not initialized")
        
        with self.get_session() as session:
            return session.execute_write(tx_function, *args, **kwargs)


# Global Neo4j manager instance
neo4j_manager = Neo4jManager()