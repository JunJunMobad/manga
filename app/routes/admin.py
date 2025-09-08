"""
Admin endpoints for manual triggers and monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.services.cron_service import cron_service
from app.services.manga_tracker_service import MangaTrackerService
from app.services.zenrows_service import zenrows_service
from app.utils.auth import get_current_user


router = APIRouter()


@router.post("/trigger/chapter-check")
async def trigger_chapter_check(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Manually trigger manga chapter checking
    
    Returns:
        Results of the chapter check operation
    """
    try:
        result = await cron_service.trigger_chapter_check()
        return {
            "success": True,
            "message": "Chapter check completed",
            "results": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger chapter check: {str(e)}"
        )


@router.post("/trigger/notifications")
async def trigger_notifications(
    day: str = "wednesday",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Manually trigger notification sending
    
    Args:
        day: "wednesday" or "saturday"
        
    Returns:
        Results of the notification operation
    """
    if day not in ["wednesday", "saturday"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Day must be 'wednesday' or 'saturday'"
        )
    
    try:
        result = await cron_service.trigger_notifications(day)
        return {
            "success": True,
            "message": f"{day.capitalize()} notifications sent",
            "results": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger notifications: {str(e)}"
        )


@router.get("/cron/status")
async def get_cron_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get cron job status information
    
    Returns:
        Status of background cron jobs
    """
    return {
        "scheduler_running": cron_service.is_running,
        "message": "Cron scheduler is running" if cron_service.is_running else "Cron scheduler is stopped"
    }


@router.get("/test-api/{manga_id}")
async def test_api_direct(manga_id: str):
    """
    Test the manga API directly without authentication
    
    Args:
        manga_id: Manga ID to test (e.g., 34oFHVI8)
        
    Returns:
        API response or error details
    """
    try:
        manga_tracker = MangaTrackerService()
        chapters = await manga_tracker._fetch_manga_chapters(manga_id)
        
        if not chapters:
            return {
                "success": False,
                "manga_id": manga_id,
                "error": "API blocked by Cloudflare protection",
                "message": "This API requires human verification (CAPTCHA). Check console logs for solutions.",
                "chapters_found": 0
            }
        
        return {
            "success": True,
            "manga_id": manga_id,
            "chapters_found": len(chapters),
            "sample_chapters": chapters[:3] if chapters else []
        }
    
    except Exception as e:
        return {
            "success": False,
            "manga_id": manga_id,
            "error": str(e)
        }


@router.get("/test-zenrows")
async def test_zenrows_connection(current_user: dict = Depends(get_current_user)):
    """
    Test ZenRows connection and configuration
    
    Returns:
        Connection test results
    """
    try:
        is_connected = zenrows_service.test_connection()
        
        return {
            "success": is_connected,
            "service": "ZenRows",
            "message": "Connection successful" if is_connected else "Connection failed",
            "configured": zenrows_service.api_key is not None
        }
    
    except Exception as e:
        return {
            "success": False,
            "service": "ZenRows", 
            "error": str(e)
        }


@router.get("/test-zenrows/{manga_id}")
async def test_zenrows_manga(manga_id: str, current_user: dict = Depends(get_current_user)):
    """
    Test ZenRows with a specific manga ID
    
    Args:
        manga_id: Manga ID to test (e.g., 34oFHVI8)
        
    Returns:
        ZenRows test results for the manga
    """
    try:
        data = await zenrows_service.fetch_manga_chapters(manga_id)
        
        if data and 'chapters' in data:
            chapters = data.get('chapters', [])
            return {
                "success": True,
                "service": "ZenRows",
                "manga_id": manga_id,
                "chapters_found": len(chapters),
                "sample_chapters": chapters[:3] if chapters else []
            }
        else:
            return {
                "success": False,
                "service": "ZenRows",
                "manga_id": manga_id,
                "error": "No chapters data returned",
                "chapters_found": 0
            }
    
    except Exception as e:
        return {
            "success": False,
            "service": "ZenRows",
            "manga_id": manga_id,
            "error": str(e)
        }