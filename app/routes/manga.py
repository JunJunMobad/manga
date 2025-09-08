"""
Manga subscription API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.schemas.requests import MangaSubscriptionRequest
from app.schemas.responses import MangaSubscriptionResponse, UserInfoResponse
from app.services.firebase_service import FirestoreService
from app.services.manga_tracker_service import MangaTrackerService
from app.utils.auth import get_current_user, get_user_id


router = APIRouter()


@router.post("/subscribe", response_model=MangaSubscriptionResponse)
async def subscribe_to_manga(
    request: MangaSubscriptionRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Subscribe user to manga notifications
    
    Args:
        request: Manga subscription request containing manga_id
        user_id: Firebase user ID from authentication
        
    Returns:
        Success response with updated subscriptions or error if already subscribed
    """
    firestore_service = FirestoreService()
    manga_tracker = MangaTrackerService()
    
    result = await firestore_service.subscribe_to_manga(user_id, request.manga_id)
    
    if not result['success']:
        if "already subscribed" in result['message']:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result['message']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    subscriptions = await firestore_service.get_user_subscriptions(user_id)
    
    return MangaSubscriptionResponse(
        success=True,
        message=result['message'],
        manga_id=request.manga_id,
        subscriptions=subscriptions
    )


@router.post("/unsubscribe", response_model=MangaSubscriptionResponse)
async def unsubscribe_from_manga(
    request: MangaSubscriptionRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Unsubscribe user from manga notifications
    
    Args:
        request: Manga subscription request containing manga_id
        user_id: Firebase user ID from authentication
        
    Returns:
        Success response with updated subscriptions or error if not subscribed
    """
    firestore_service = FirestoreService()
    
    result = await firestore_service.unsubscribe_from_manga(user_id, request.manga_id)
    
    if not result['success']:
        if "did not subscribe" in result['message'] or "no manga subscriptions" in result['message']:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result['message']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    subscriptions = await firestore_service.get_user_subscriptions(user_id)
    
    return MangaSubscriptionResponse(
        success=True,
        message=result['message'],
        manga_id=request.manga_id,
        subscriptions=subscriptions
    )


@router.get("/subscriptions", response_model=UserInfoResponse)
async def get_user_subscriptions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get user's current manga subscriptions
    
    Args:
        current_user: Authenticated user information
        
    Returns:
        user subscriptions
    """
    firestore_service = FirestoreService()
    user_id = current_user.get("uid")
    
    subscriptions = await firestore_service.get_user_subscriptions(user_id)
    
    return UserInfoResponse(
        user_id=user_id,       
        subscriptions=subscriptions
    )