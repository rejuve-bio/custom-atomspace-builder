"""Background tasks for application maintenance."""

import asyncio
from ..core.session_manager import session_manager


async def session_cleanup_worker():
    """Background task to cleanup expired upload sessions."""
    while True:
        try:
            expired_count = session_manager.cleanup_expired_sessions()
            
            if expired_count > 0:
                print(f"Cleaned up {expired_count} expired upload sessions")
                
        except asyncio.CancelledError:
            print("Session cleanup task cancelled")
            break
        except Exception as e:
            print(f"Error in session cleanup: {e}")
        
        await asyncio.sleep(300)  # Check every 5 minutes