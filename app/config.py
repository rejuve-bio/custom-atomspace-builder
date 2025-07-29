"""Configuration management for the AtomSpace Builder API."""

import os
import yaml
from pathlib import Path
from datetime import timedelta
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables and config file."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._load_config()
        self._load_env_settings()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Warning: Config file {self.config_path} not found. Using defaults.")
            self._config = self._get_default_config()
    
    def _load_env_settings(self):
        """Load settings from environment variables."""
        # HugeGraph settings
        self.hugegraph_loader_path = self._config['paths']['hugegraph_loader']
        self.hugegraph_host = os.getenv('HUGEGRAPH_HOST', 'localhost')
        self.hugegraph_port = os.getenv('HUGEGRAPH_PORT', '8080')
        self.hugegraph_graph = os.getenv('HUGEGRAPH_GRAPH', 'hugegraph')
        
        # Directories
        self.base_output_dir = os.path.abspath(self._config['paths']['output_dir'])
        self.selected_job_file = os.path.join(self.base_output_dir, "selected_job.txt")
        
        # Session settings
        self.session_timeout = timedelta(hours=self._config['uploads']['session_timeout'])
        
        # Annotation service
        self.annotation_service_url = os.getenv('ANNOTATION_SERVICE_URL')
        self.annotation_service_timeout = float(os.getenv('ANNOTATION_SERVICE_TIMEOUT', '300'))
        
        # Neo4j settings
        self.neo4j_config = {
            "host": os.getenv('NEO4J_HOST', 'localhost'),
            "port": int(os.getenv('NEO4J_PORT')),
            "username": os.getenv('NEO4J_USERNAME', 'neo4j'),
            "password": os.getenv('NEO4J_PASSWORD'),
            "database": os.getenv('NEO4J_DATABASE', 'neo4j')
        }
        
        # CORS settings
        self.cors_allow_origins = self._config['cors']['allow_origins']
        self.cors_allow_credentials = self._config['cors']['allow_credentials']
        self.cors_allow_methods = self._config['cors']['allow_methods']
        self.cors_allow_headers = self._config['cors']['allow_headers']
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if config file is not found."""
        return {
            'paths': {
                'hugegraph_loader': './bin/hugegraph-loader.sh',
                'output_dir': './output'
            },
            'uploads': {
                'session_timeout': 24
            },
            'cors': {
                'allow_origins': ["*"],
                'allow_credentials': True,
                'allow_methods': ["*"],
                'allow_headers': ["*"]
            }
        }
    
    @property
    def neo4j_uri(self) -> str:
        """Get Neo4j connection URI."""
        return f"bolt://{self.neo4j_config['host']}:{self.neo4j_config['port']}"
    
    @property
    def neo4j_auth(self) -> tuple:
        """Get Neo4j authentication tuple."""
        return (self.neo4j_config['username'], self.neo4j_config['password'])


# Global settings instance
settings = Settings()