"""Authentication utilities for the Call Analytics API."""

from fastapi import Depends, HTTPException, Header, status
from backend.common.config import get_settings, Settings


def verify_api_key(
    x_api_key: str | None = Header(None),
    settings: Settings = Depends(get_settings)
) -> bool:
    """
    Verify the API key from the X-API-Key header.
    
    This dependency should be added to all protected endpoints to ensure
    only authorized clients can access sensitive data.
    
    Args:
        x_api_key: The API key provided in the X-API-Key header
        settings: Application settings containing the valid API key
        
    Returns:
        bool: True if the key is valid (dependency passes)
        
    Raises:
        HTTPException: If the key is missing, invalid, or server is misconfigured
    """
    # Check if the server is properly configured
    if not settings.call_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is not properly configured: CALL_API_KEY is not set"
        )
    
    # Check if the client provided an API key
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Verify the API key
    if x_api_key != settings.call_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Key is valid
    return True