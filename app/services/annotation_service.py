"""Annotation service communication."""

import httpx
from typing import Optional
from ..config import settings


class AnnotationService:
    """Service for communicating with the annotation service."""
    
    def __init__(self):
        self.service_url = settings.annotation_service_url
        self.timeout = settings.annotation_service_timeout
    
    async def notify_annotation_service(self, job_id: str, writer_type: str) -> Optional[str]:
        """Notify the annotation service about a new job."""
        if not self.service_url:
            print("Error: ANNOTATION_SERVICE_URL not configured")
            raise RuntimeError("Annotation service URL is not set")
        if writer_type == "neo4j":
            writer_type = "cypher"
        
        payload = {"folder_id": job_id, "type": writer_type}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.service_url,
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    error_msg = f"Annotation service returned {response.status_code}: {response.text}"
                    print(f"Error connecting to the Annotation: {error_msg}")
                    raise RuntimeError(error_msg)
                    
        except httpx.TimeoutException as e:
            error_msg = "Timeout connecting to annotation service"
            print(f"Error connecting to the Annotation: {error_msg}: {str(e)}")
            raise RuntimeError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to connect to annotation service: {str(e)}"
            print(f"Error connecting to the Annotation: {error_msg}")
            raise RuntimeError(error_msg)
        
        return None


# Global service instance
annotation_service = AnnotationService()