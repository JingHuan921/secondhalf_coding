"""
health.py

Defines the health check endpoint for the API.

This endpoint can be used by monitoring tools or load balancers to verify that the service is running and responsive.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health", response_class=JSONResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns a simple JSON response indicating the service is healthy.
    Can be used for uptime monitoring and automated health checks.
    """
    return {"status": "ok"}
