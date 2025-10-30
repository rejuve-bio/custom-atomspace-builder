"""Webhook service for sending status updates."""

import httpx
import logging
from datetime import datetime
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook status types."""
    STARTED = "started"
    PROCESSING = "processing"
    LOADING = "loading"
    COMPLETED = "completed"
    FAILED = "failed"


class WebhookService:
    """Service for sending webhook notifications."""
    
    TIMEOUT = 10.0  # seconds
    
    @staticmethod
    async def send_status(
        webhook_url: str,
        status: WebhookStatus,
        job_id: str = "",
        message: str = "",
        error: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """Send status update to webhook URL.
        
        Args:
            webhook_url: The webhook endpoint URL
            status: WebhookStatus enum value
            job_id: Job identifier
            message: Human-readable message
            error: Error message if applicable
            metadata: Additional data to include in payload
        """
        if not webhook_url:
            return
        
        payload = {
            "status": status.value,
            "job_id": job_id,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            payload["error"] = error
        
        if metadata:
            payload["metadata"] = metadata
        
        try:
            async with httpx.AsyncClient(timeout=WebhookService.TIMEOUT) as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Webhook sent successfully to {webhook_url} with status {status.value}")
                
        except httpx.RequestError as e:
            logger.warning(f"Failed to send webhook to {webhook_url}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending webhook to {webhook_url}: {str(e)}")
    
    @staticmethod
    async def send_started(webhook_url: str, message: str = "Job processing started"):
        """Send started status."""
        await WebhookService.send_status(webhook_url, WebhookStatus.STARTED, message=message)
    
    @staticmethod
    async def send_processing(webhook_url: str, job_id: str = "", message: str = "Processing data"):
        """Send processing status."""
        await WebhookService.send_status(webhook_url, WebhookStatus.PROCESSING, job_id=job_id, message=message)
    
    @staticmethod
    async def send_loading(webhook_url: str, job_id: str, message: str = "Loading to database"):
        """Send loading status."""
        await WebhookService.send_status(webhook_url, WebhookStatus.LOADING, job_id=job_id, message=message)
    
    @staticmethod
    async def send_completed(webhook_url: str, job_id: str, message: str, metadata: Optional[dict] = None):
        """Send completed status."""
        await WebhookService.send_status(
            webhook_url, 
            WebhookStatus.COMPLETED, 
            job_id=job_id, 
            message=message,
            metadata=metadata
        )
    
    @staticmethod
    async def send_failed(webhook_url: str, job_id: str = "", error: str = ""):
        """Send failed status."""
        await WebhookService.send_status(
            webhook_url, 
            WebhookStatus.FAILED, 
            job_id=job_id, 
            error=error
        )


# Create singleton instance
webhook_service = WebhookService()