"""File parsing service for handling CSV preprocessing and caching."""

import os
import json
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone

from ..models.schemas import DataSource, FileInfo
from ..core.session_manager import session_manager
from ..utils.file_utils import (
    preprocess_csv_file, 
    is_csv_file
)


class FileParserService:
    """Service for parsing and caching file data sources."""
    
    CACHE_FILENAME = "datasources_cache.json"
    
    def __init__(self):
        """Initialize the file parser service."""
        pass
    
    def get_cache_path(self, session_id: str) -> str:
        """Get the path to the datasources cache file for a session."""
        session_dir = session_manager._get_session_dir(session_id)
        return os.path.join(session_dir, self.CACHE_FILENAME)
    
    def load_cache(self, session_id: str) -> Dict[str, DataSource]:
        """Load cached datasources from JSON file."""
        cache_path = self.get_cache_path(session_id)
        
        if not os.path.exists(cache_path):
            return {}
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # Convert back to DataSource objects
            datasources = {}
            for filename, data in cache_data.items():
                datasources[filename] = DataSource(**data)
                
            return datasources
        except Exception as e:
            print(f"Error loading datasources cache for session {session_id}: {str(e)}")
            return {}
    
    def save_cache(self, session_id: str, datasources: Dict[str, DataSource]) -> bool:
        """Save datasources cache to JSON file."""
        cache_path = self.get_cache_path(session_id)
        
        try:
            # Ensure session directory exists
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            # Convert DataSource objects to dict for JSON serialization
            cache_data = {}
            for filename, datasource in datasources.items():
                cache_data[filename] = datasource.model_dump()
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
            return True
        except Exception as e:
            print(f"Error saving datasources cache for session {session_id}: {str(e)}")
            return False
    
    def update_cache_with_new_files(self, session_id: str, new_files: List[str]) -> bool:
        """Update datasources cache with newly uploaded files."""
        if not new_files:
            return True
        
        # Load existing cache
        cached_datasources = self.load_cache(session_id)
        
        # Process only new CSV files
        session_dir = session_manager._get_session_dir(session_id)
        updated = False
        
        for filename in new_files:
            if is_csv_file(filename):
                file_path = os.path.join(session_dir, filename)
                if os.path.exists(file_path):
                    datasource = preprocess_csv_file(file_path, filename)
                    if datasource:
                        cached_datasources[filename] = datasource
                        updated = True
        
        # Save updated cache
        if updated:
            return self.save_cache(session_id, cached_datasources)
        
        return True
    
    def remove_from_cache(self, session_id: str, filename: str) -> bool:
        """Remove a file's datasource from cache when file is deleted."""
        cached_datasources = self.load_cache(session_id)
        
        if filename in cached_datasources:
            del cached_datasources[filename]
            return self.save_cache(session_id, cached_datasources)
        
        return True
    
    def get_all_datasources(self, session_id: str) -> List[DataSource]:
        """Get all datasources for a session, using cache when possible."""
        session = session_manager.get_session(session_id)
        if not session:
            return []
        
        # Load cached datasources
        cached_datasources = self.load_cache(session_id)
        
        # Check if we need to process any new files
        new_files = []
        for filename in session.uploaded_files:
            if is_csv_file(filename) and filename not in cached_datasources:
                new_files.append(filename)
        
        # Process new files if any
        if new_files:
            self.update_cache_with_new_files(session_id, new_files)
            # Reload cache after update
            cached_datasources = self.load_cache(session_id)
        
        # Filter out datasources for files that no longer exist in session
        valid_datasources = []
        for filename in session.uploaded_files:
            if filename in cached_datasources:
                valid_datasources.append(cached_datasources[filename])
        
        return valid_datasources
    
    def process_uploaded_files(self, session_id: str, filenames: List[str]) -> bool:
        """Process multiple uploaded files and update cache."""
        return self.update_cache_with_new_files(session_id, filenames)
    
    def get_datasource_by_filename(self, session_id: str, filename: str) -> Optional[DataSource]:
        """Get a specific datasource by filename."""
        cached_datasources = self.load_cache(session_id)
        return cached_datasources.get(filename)
    
    def refresh_datasource(self, session_id: str, filename: str) -> Optional[DataSource]:
        """Force refresh a specific datasource by reprocessing the file."""
        if not is_csv_file(filename):
            return None
        
        session_dir = session_manager._get_session_dir(session_id)
        file_path = os.path.join(session_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        # Reprocess the file
        datasource = preprocess_csv_file(file_path, filename)
        if datasource:
            # Update cache
            cached_datasources = self.load_cache(session_id)
            cached_datasources[filename] = datasource
            self.save_cache(session_id, cached_datasources)
        
        return datasource
    
    def clear_cache(self, session_id: str) -> bool:
        """Clear all cached datasources for a session."""
        cache_path = self.get_cache_path(session_id)
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
            return True
        except Exception as e:
            print(f"Error clearing cache for session {session_id}: {str(e)}")
            return False
    
    def get_cache_stats(self, session_id: str) -> Dict[str, any]:
        """Get cache statistics for debugging."""
        cache_path = self.get_cache_path(session_id)
        
        stats = {
            "cache_exists": os.path.exists(cache_path),
            "cache_path": cache_path,
            "cached_files_count": 0,
            "cache_size_bytes": 0,
            "last_modified": None
        }
        
        if os.path.exists(cache_path):
            try:
                cache_stat = os.stat(cache_path)
                stats["cache_size_bytes"] = cache_stat.st_size
                stats["last_modified"] = datetime.fromtimestamp(
                    cache_stat.st_mtime, tz=timezone.utc
                ).isoformat()
                
                cached_datasources = self.load_cache(session_id)
                stats["cached_files_count"] = len(cached_datasources)
            except Exception as e:
                stats["error"] = str(e)
        
        return stats


# Global instance
file_parser_service = FileParserService()