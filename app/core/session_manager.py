"""Upload session management."""

import os
import shutil
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional
from ..models.schemas import UploadSession
from ..models.enums import SessionStatus
from ..config import settings


class SessionManager:
    """Manages upload sessions with automatic cleanup."""
    
    def __init__(self):
        self.sessions: Dict[str, UploadSession] = {}
    
    def create_session(self) -> str:
        """Create a new upload session."""
        session_id = secrets.token_urlsafe(32)
        session = UploadSession(
            session_id=session_id,
            created_at=datetime.now(tz=timezone.utc),
            expires_at=datetime.now(tz=timezone.utc) + settings.session_timeout,
            uploaded_files=[],
            status=SessionStatus.ACTIVE
        )
        
        self.sessions[session_id] = session
        
        # Create session directory
        session_dir = self._get_session_dir(session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[UploadSession]:
        """Get an active session by ID."""
        session = self.sessions.get(session_id)
        
        if not session:
            return None
            
        if session.expires_at > datetime.now(tz=timezone.utc):
            return session
        else:
            # Mark as expired
            session.status = SessionStatus.EXPIRED
            return None
    
    def add_file_to_session(self, session_id: str, filename: str) -> bool:
        """Add a file to an existing session."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        if filename not in session.uploaded_files:
            session.uploaded_files.append(filename)
        
        return True
    
    def remove_file_from_session(self, session_id: str, filename: str) -> bool:
        """Remove a file from a session."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        try:
            session.uploaded_files.remove(filename)
            
            # Remove physical file
            file_path = os.path.join(self._get_session_dir(session_id), filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except ValueError:
            return False
    
    def consume_session(self, session_id: str) -> bool:
        """Mark session as consumed (used for job processing)."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.CONSUMED
        return True
    
    def cleanup_session(self, session_id: str):
        """Clean up session files and directory."""
        session_dir = self._get_session_dir(session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
        
        # Remove from active sessions
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up all expired sessions and return count."""
        now = datetime.now(tz=timezone.utc)
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if session.expires_at < now and session.status == SessionStatus.ACTIVE
        ]
        
        for session_id in expired_sessions:
            self.sessions[session_id].status = SessionStatus.EXPIRED
            self.cleanup_session(session_id)
        
        return len(expired_sessions)
    
    def _get_session_dir(self, session_id: str) -> str:
        """Get the directory path for a session."""
        return os.path.join(settings.base_output_dir, "uploads", session_id)
    
    def get_session_files_info(self, session_id: str) -> list:
        """Get information about files in a session."""
        session = self.get_session(session_id)
        if not session:
            return []
        
        session_dir = self._get_session_dir(session_id)
        file_details = []
        
        for filename in session.uploaded_files:
            file_path = os.path.join(session_dir, filename)
            if os.path.exists(file_path):
                file_details.append({
                    "filename": filename,
                    "size": os.path.getsize(file_path),
                    "status": "uploaded"
                })
        
        return file_details


# Global session manager instance
session_manager = SessionManager()