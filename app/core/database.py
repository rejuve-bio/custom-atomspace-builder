"""Database connection management for Neo4j with delayed deployment handling."""

import time
import threading
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
from typing import Optional, Callable, Any
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Manages Neo4j database connections with retry logic for delayed deployment."""
    
    def __init__(self, max_retries: int = 30, retry_interval: int = 5):
        self.driver: Optional[GraphDatabase] = None
        self._initialized = False
        self._connection_lock = threading.Lock()
        self._initialization_thread: Optional[threading.Thread] = None
        
        # Retry configuration
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self._retry_count = 0
        self._last_connection_attempt = 0
        
        # Start background initialization
        self._start_background_initialization()
    
    def _start_background_initialization(self):
        """Start background thread to initialize Neo4j connection."""
        if self._initialization_thread is None or not self._initialization_thread.is_alive():
            self._initialization_thread = threading.Thread(
                target=self._initialize_with_retries,
                daemon=True
            )
            self._initialization_thread.start()
    
    def _initialize_with_retries(self):
        """Initialize Neo4j driver with retry logic."""
        logger.info("Starting Neo4j connection attempts...")
        
        while self._retry_count < self.max_retries and not self._initialized:
            try:
                with self._connection_lock:
                    if self._initialized:  # Double-check after acquiring lock
                        break
                        
                    logger.info(f"Attempting Neo4j connection (attempt {self._retry_count + 1}/{self.max_retries})")
                    
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
                    
                    logger.info("Neo4j driver initialized successfully")
                    self._initialized = True
                    self._retry_count = 0
                    return True
                    
            except (ServiceUnavailable, AuthError, Exception) as e:
                logger.warning(f"Neo4j connection attempt {self._retry_count + 1} failed: {e}")
                
                if self.driver:
                    try:
                        self.driver.close()
                    except Exception:
                        pass
                    self.driver = None
                
                self._retry_count += 1
                self._last_connection_attempt = time.time()
                
                if self._retry_count < self.max_retries:
                    logger.info(f"Retrying Neo4j connection in {self.retry_interval} seconds...")
                    time.sleep(self.retry_interval)
                else:
                    logger.error(f"Failed to connect to Neo4j after {self.max_retries} attempts")
                    break
        
        return False
    
    def initialize_driver(self) -> bool:
        """Initialize the Neo4j driver (synchronous version for compatibility)."""
        if self._initialized:
            return True
        
        # If background initialization is running, wait a bit for it
        if self._initialization_thread and self._initialization_thread.is_alive():
            self._initialization_thread.join(timeout=1.0)
        
        if not self._initialized:
            # Try immediate initialization
            return self._initialize_with_retries()
        
        return self._initialized
    
    def close_driver(self):
        """Close the Neo4j driver connection."""
        with self._connection_lock:
            if self.driver:
                self.driver.close()
                logger.info("Neo4j driver closed")
            self._initialized = False
            self.driver = None
    
    def is_connected(self) -> bool:
        """Check if Neo4j driver is properly initialized."""
        return self._initialized and self.driver is not None
    
    def wait_for_connection(self, timeout: float = 60.0) -> bool:
        """Wait for Neo4j connection to be established."""
        start_time = time.time()
        
        while not self._initialized and (time.time() - start_time) < timeout:
            if self._initialization_thread and self._initialization_thread.is_alive():
                self._initialization_thread.join(timeout=1.0)
            else:
                # Restart background initialization if it stopped
                self._start_background_initialization()
            time.sleep(0.5)
        
        return self._initialized
    
    def get_session(self):
        """Get a Neo4j session. Use in context manager."""
        if not self.is_connected():
            # Try to reconnect if connection was lost
            if time.time() - self._last_connection_attempt > self.retry_interval:
                self._start_background_initialization()
            raise RuntimeError("Neo4j driver is not initialized. Connection may still be establishing.")
        
        return self.driver.session(database=settings.neo4j_config.get("database"))
    
    def execute_query(self, query: str, parameters: dict = None, wait_for_connection: bool = True):
        """Execute a single query and return results."""
        if not self.is_connected():
            if wait_for_connection:
                logger.info("Waiting for Neo4j connection before executing query...")
                if not self.wait_for_connection(timeout=30.0):
                    raise RuntimeError("Neo4j connection not available after waiting")
            else:
                raise RuntimeError("Neo4j driver is not initialized")
        
        try:
            with self.get_session() as session:
                result = session.run(query, parameters or {})
                return list(result)
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            # Reset connection status to trigger reconnection
            with self._connection_lock:
                self._initialized = False
            raise RuntimeError("Neo4j service is currently unavailable")
    
    def execute_transaction(self, tx_function: Callable, *args, wait_for_connection: bool = True, **kwargs):
        """Execute a transaction function."""
        if not self.is_connected():
            if wait_for_connection:
                logger.info("Waiting for Neo4j connection before executing transaction...")
                if not self.wait_for_connection(timeout=30.0):
                    raise RuntimeError("Neo4j connection not available after waiting")
            else:
                raise RuntimeError("Neo4j driver is not initialized")
        
        try:
            with self.get_session() as session:
                return session.execute_write(tx_function, *args, **kwargs)
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            # Reset connection status to trigger reconnection
            with self._connection_lock:
                self._initialized = False
            raise RuntimeError("Neo4j service is currently unavailable")
    
    def execute_query_safe(self, query: str, parameters: dict = None, default_return: Any = None):
        """Execute query with graceful failure handling."""
        try:
            return self.execute_query(query, parameters, wait_for_connection=False)
        except RuntimeError as e:
            logger.warning(f"Neo4j query failed gracefully: {e}")
            return default_return
    
    def health_check(self) -> dict:
        """Return health status of Neo4j connection."""
        status = {
            "connected": self._initialized,
            "retry_count": self._retry_count,
            "max_retries": self.max_retries,
            "driver_available": self.driver is not None,
            "background_init_running": self._initialization_thread and self._initialization_thread.is_alive()
        }
        
        if self._initialized:
            try:
                with self.get_session() as session:
                    result = session.run("RETURN 1 as test").single()
                    status["test_query"] = "success"
            except Exception as e:
                status["test_query"] = f"failed: {str(e)}"
                
        return status


# Global Neo4j manager instance
neo4j_manager = Neo4jManager()