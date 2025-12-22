"""Database service for MongoDB operations."""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from ..core.mongodb import get_database
from ..models.schemas import (
    JobMetadata, GraphInfo, AnnotationSchema, SchemaDefinition
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for MongoDB database operations."""    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        """Get database instance."""
        if self.db is None:
            try:
                self.db = get_database()
                logger.info("MongoDB database instance obtained successfully")
            except RuntimeError as e:
                logger.critical(f"CRITICAL ERROR: {e}")
                logger.critical("MongoDB connection was not established on startup!")
                raise
        return self.db
    
    # Job Metadata Operations
    async def save_job_metadata(self, job_id: str, writer_type: str, neo4j_config: Optional[Dict[str, Any]] = None) -> None:
        """Save job metadata to database."""
        try:
            db = self._get_db()
            job_metadata = {
                "job_id": job_id,
                "writer_type": writer_type,
                "created_at": str(datetime.now(tz=timezone.utc)),
                "neo4j_config": neo4j_config,
                "updated_at": str(datetime.now(tz=timezone.utc))
            }
            result = await db.job_metadata.replace_one(
                {"job_id": job_id},
                job_metadata,
                upsert=True
            )
            logger.info(f"Saved job_metadata to MongoDB for job_id: {job_id}")
        except Exception as e:
            logger.error(f"ERROR saving job_metadata to MongoDB: {e}", exc_info=True)
            raise
    
    async def get_job_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job metadata from database."""
        db = self._get_db()
        result = await db.job_metadata.find_one({"job_id": job_id})
        if result:
            result.pop("_id", None)  # Remove MongoDB _id
        return result
    
    # Schema Operations
    async def save_schema(self, job_id: str, schema_data: Dict[str, Any]) -> None:
        """Save schema to database."""
        try:
            db = self._get_db()
            schema_doc = {
                "job_id": job_id,
                "schema": schema_data,
                "created_at": str(datetime.now(tz=timezone.utc)),
                "updated_at": str(datetime.now(tz=timezone.utc))
            }
            await db.schemas.replace_one(
                {"job_id": job_id},
                schema_doc,
                upsert=True
            )
            logger.info(f"Saved schema to MongoDB for job_id: {job_id}")
        except Exception as e:
            logger.error(f"ERROR saving schema to MongoDB: {e}", exc_info=True)
            raise
    
    async def get_schema(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get schema from database."""
        db = self._get_db()
        result = await db.schemas.find_one({"job_id": job_id})
        if result:
            return result.get("schema")
        return None
    
    # Graph Info Operations
    async def save_graph_info(self, graph_info: GraphInfo) -> None:
        """Save graph information to database."""
        try:
            db = self._get_db()
            graph_info_doc = graph_info.dict()
            graph_info_doc["updated_at"] = str(datetime.now(tz=timezone.utc))
            await db.graph_info.replace_one(
                {"job_id": graph_info.job_id},
                graph_info_doc,
                upsert=True
            )
            logger.info(f"Saved graph_info to MongoDB for job_id: {graph_info.job_id}")
        except Exception as e:
            logger.error(f"ERROR saving graph_info to MongoDB: {e}", exc_info=True)
            raise
    
    async def get_graph_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get graph information from database."""
        db = self._get_db()
        result = await db.graph_info.find_one({"job_id": job_id})
        if result:
            result.pop("_id", None)  # Remove MongoDB _id
        return result
    
    # Graph Metadata Operations
    async def save_graph_metadata(self, job_id: str, metadata: Dict[str, Any]) -> None:
        """Save graph metadata to database."""
        db = self._get_db()
        metadata_doc = {
            "job_id": job_id,
            "metadata": metadata,
            "created_at": str(datetime.now(tz=timezone.utc)),
            "updated_at": str(datetime.now(tz=timezone.utc))
        }
        await db.graph_metadata.replace_one(
            {"job_id": job_id},
            metadata_doc,
            upsert=True
        )
    
    async def get_graph_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get graph metadata from database."""
        db = self._get_db()
        result = await db.graph_metadata.find_one({"job_id": job_id})
        if result:
            return result.get("metadata")
        return None
    
    # Annotation Schema Operations
    async def save_annotation_schema(self, job_id: str, annotation_schema: Dict[str, Any]) -> None:
        """Save annotation schema to database."""
        db = self._get_db()
        annotation_doc = {
            "job_id": job_id,
            "annotation_schema": annotation_schema,
            "created_at": str(datetime.now(tz=timezone.utc)),
            "updated_at": str(datetime.now(tz=timezone.utc))
        }
        await db.annotation_schemas.replace_one(
            {"job_id": job_id},
            annotation_doc,
            upsert=True
        )
    
    async def get_annotation_schema(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get annotation schema from database."""
        db = self._get_db()
        result = await db.annotation_schemas.find_one({"job_id": job_id})
        if result:
            return result.get("annotation_schema")
        return None
    
    # History Operations
    async def get_history(self) -> Dict[str, Any]:
        """Get job processing history."""
        db = self._get_db()
        result = await db.history.find_one({"type": "main"})
        if result:
            result.pop("_id", None)
            result.pop("type", None)
            return result
        return {"selected_job_id": "", "history": []}
    
    async def save_history(self, history: Dict[str, Any]) -> None:
        """Save job processing history."""
        try:
            db = self._get_db()
            history_doc = {
                "type": "main",
                "selected_job_id": history.get("selected_job_id", ""),
                "history": history.get("history", []),
                "updated_at": str(datetime.now(tz=timezone.utc))
            }
            await db.history.replace_one(
                {"type": "main"},
                history_doc,
                upsert=True
            )
            logger.info(f"Saved history to MongoDB (entries: {len(history.get('history', []))})")
        except Exception as e:
            logger.error(f"ERROR saving history to MongoDB: {e}", exc_info=True)
            raise
    
    async def clear_history(self) -> Dict[str, Any]:
        """Clear the history."""
        history = {"selected_job_id": "", "history": []}
        await self.save_history(history)
        return history
    
    # Selected Job Operations
    async def get_selected_job_id(self) -> Optional[str]:
        """Get the currently selected job ID."""
        history = await self.get_history()
        selected_id = history.get("selected_job_id", "")
        return selected_id if selected_id else None
    
    async def save_selected_job_id(self, job_id: str) -> None:
        """Save the selected job ID."""
        history = await self.get_history()
        history["selected_job_id"] = job_id
        await self.save_history(history)
    
    # Job Deletion Operations
    async def delete_job(self, job_id: str) -> None:
        """Delete all data associated with a job."""
        db = self._get_db()
        # Delete all collections for this job
        await db.job_metadata.delete_one({"job_id": job_id})
        await db.schemas.delete_one({"job_id": job_id})
        await db.graph_info.delete_one({"job_id": job_id})
        await db.graph_metadata.delete_one({"job_id": job_id})
        await db.annotation_schemas.delete_one({"job_id": job_id})
    
    async def delete_job_from_history(self, job_id: str) -> tuple[Dict[str, Any], bool]:
        """Delete a job from history and return updated history and if selected job was affected."""
        history = await self.get_history()
        selected_job_affected = False
        
        selected_job_id = history.get("selected_job_id", "")
        if selected_job_id == job_id:
            selected_job_affected = True
            history["selected_job_id"] = ""
        
        original_count = len(history["history"])
        history["history"] = [
            item for item in history["history"] 
            if item.get("job_id") != job_id
        ]
        
        if len(history["history"]) != original_count or selected_job_affected:
            await self.save_history(history)
        
        return history, selected_job_affected


# Global service instance
database_service = DatabaseService()

