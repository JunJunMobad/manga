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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
            "results": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger chapter check: {str(e)}",
        )


@router.post("/trigger/notifications")
async def trigger_notifications(
    day: str = "wednesday", current_user: Dict[str, Any] = Depends(get_current_user)
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
            detail="Day must be 'wednesday' or 'saturday'",
        )

    try:
        result = await cron_service.trigger_notifications(day)
        return {
            "success": True,
            "message": f"{day.capitalize()} notifications sent",
            "results": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger notifications: {str(e)}",
        )


@router.get("/cron/status")
async def get_cron_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get cron job status information

    Returns:
        Status of background cron jobs
    """
    return {
        "scheduler_running": cron_service.is_running,
        "message": (
            "Cron scheduler is running"
            if cron_service.is_running
            else "Cron scheduler is stopped"
        ),
    }


@router.get("/test-api/{manga_hid}")
async def test_api_direct(manga_hid: str):
    """
    Test the manga API directly without authentication

    Args:
        manga_hid: Manga HID to test

    Returns:
        API response or error details
    """
    try:
        manga_tracker = MangaTrackerService()
        chapters = await manga_tracker._fetch_manga_chapters(manga_hid)

        if not chapters:
            return {
                "success": False,
                "manga_hid": manga_hid,
                "error": "API blocked by Cloudflare protection",
                "message": "This API requires human verification (CAPTCHA). Check console logs for solutions.",
                "chapters_found": 0,
            }

        return {
            "success": True,
            "manga_hid": manga_hid,
            "chapters_found": len(chapters),
            "first_chapters": chapters[:3] if chapters else [],
        }

    except Exception as e:
        return {"success": False, "manga_hid": manga_hid, "error": str(e)}


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
            "configured": zenrows_service.api_key is not None,
        }

    except Exception as e:
        return {"success": False, "service": "ZenRows", "error": str(e)}


@router.get("/test-zenrows/{manga_hid}")
async def test_zenrows_manga(
    manga_hid: str, current_user: dict = Depends(get_current_user)
):
    """
    Test ZenRows with a specific manga HID

    Args:
        manga_hid: Manga HID

    Returns:
        ZenRows test results for the manga
    """
    try:
        data = await zenrows_service.fetch_manga_chapters(manga_hid)

        if data and "chapters" in data:
            chapters = data.get("chapters", [])
            return {
                "success": True,
                "service": "ZenRows",
                "manga_hid": manga_hid,
                "chapters_found": len(chapters),
                "first_chapters": chapters[:3] if chapters else [],
            }
        else:
            return {
                "success": False,
                "service": "ZenRows",
                "manga_hid": manga_hid,
                "error": "No chapters data returned",
                "chapters_found": 0,
            }

    except Exception as e:
        return {
            "success": False,
            "service": "ZenRows",
            "manga_hid": manga_hid,
            "error": str(e),
        }


@router.get("/test-manga-info/{manga_id}")
async def test_manga_info_fetch(
    manga_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Test fetching manga info

    Args:
        manga_id: Manga ID

    Returns:
        Manga info fetch results including HID and title
    """
    try:
        manga_info = await zenrows_service.fetch_manga_info(manga_id)

        if manga_info:
            return {
                "success": True,
                "service": "ZenRows",
                "manga_id": manga_id,
                "hid": manga_info["hid"],
                "title": manga_info["title"],
                "api_url": f"https://api.comick.fun/comic/{manga_id}/",
            }
        else:
            return {
                "success": False,
                "service": "ZenRows",
                "manga_id": manga_id,
                "error": "Could not fetch manga info",
                "api_url": f"https://api.comick.fun/comic/{manga_id}/",
            }

    except Exception as e:
        return {
            "success": False,
            "service": "ZenRows",
            "manga_id": manga_id,
            "error": str(e),
        }


@router.get("/test-chapters-by-id/{manga_id}")
async def test_chapters_by_manga_id(
    manga_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Test fetching chapters by manga ID

    Args:
        manga_id: Manga ID from client

    Returns:
        Chapter fetch results after ID to HID conversion
    """
    try:
        manga_info = await zenrows_service.fetch_manga_info(manga_id)

        if not manga_info:
            return {
                "success": False,
                "manga_id": manga_id,
                "error": "Could not fetch manga info to get HID",
                "step": "ID to HID conversion failed",
            }

        manga_hid = manga_info["hid"]
        manga_title = manga_info["title"]

        data = await zenrows_service.fetch_manga_chapters(manga_hid)

        if data and "chapters" in data:
            chapters = data.get("chapters", [])
            return {
                "success": True,
                "service": "ZenRows",
                "manga_id": manga_id,
                "manga_hid": manga_hid,
                "manga_title": manga_title,
                "chapters_found": len(chapters),
                "first_chapters": chapters[:3] if chapters else [],
            }
        else:
            return {
                "success": False,
                "service": "ZenRows",
                "manga_id": manga_id,
                "manga_hid": manga_hid,
                "manga_title": manga_title,
                "error": "No chapters data returned",
                "chapters_found": 0,
            }

    except Exception as e:
        return {
            "success": False,
            "service": "ZenRows",
            "manga_id": manga_id,
            "error": str(e),
        }
