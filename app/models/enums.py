"""Enumerations for the AtomSpace Builder API."""

from enum import Enum


class WriterType(str, Enum):
    """Supported writer types for graph generation."""
    METTA = "metta"  
    NEO4J = "neo4j"  
    MORK = "mork"  
    NETWORKX = "networkx"


class SessionStatus(str, Enum):
    """Upload session status values."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class JobStatus(str, Enum):
    """Job processing status values."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileType(str, Enum):
    """Supported file types for uploads."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    XML = "xml"