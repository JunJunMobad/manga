"""
Notification-related API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.schemas.requests import FCMTokenRequest, NotificationRequest, TestNotificationRequest
from app.schemas.responses import FCMTokenResponse, NotificationResponse
from app.services.firebase_service import FirestoreService
from app.services.notification_service import NotificationService
from app.utils.auth import get_current_user, get_user_id


router = APIRouter()


@router.post("/token", response_model=FCMTokenResponse)
async def save_fcm_token(
    request: FCMTokenRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Save or update FCM token for authenticated user
    
    Args:
        request: FCM token request containing the registration token
        user_id: Firebase user ID from authentication
        
    Returns:
        Success response
    """
    firestore_service = FirestoreService()
    
    success = await firestore_service.save_fcm_token(user_id, request.fcm_token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save FCM token"
        )
    
    return FCMTokenResponse(
        success=True,
        message="FCM token saved successfully"
    )


@router.post("/send", response_model=NotificationResponse)
async def send_manga_notification(
    request: NotificationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send notification to users subscribed to a specific manga
    
    Args:
        request: Notification request with manga_id, title, body, and optional data
        current_user: Authenticated user information
        
    Returns:
        Notification sending results
    """
    notification_service = NotificationService()
    
    result = await notification_service.send_manga_notification(
        manga_id=request.manga_id,
        title=request.title,
        body=request.body,
        data=request.data
    )
    
    return NotificationResponse(
        success=True,
        message=result["message"],
        subscribers_count=result.get("subscribers_count"),
        tokens_count=result.get("tokens_count"),
        fcm_response=result.get("fcm_response")
    )


@router.post("/test", response_model=NotificationResponse)
async def send_test_notification(
    request: TestNotificationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send test notification to specific FCM tokens (for testing purposes)
    
    Args:
        request: Test notification request with tokens, title, body, and optional data
        current_user: Authenticated user information
        
    Returns:
        Notification sending results
    """
    notification_service = NotificationService()
    
    result = await notification_service.send_notification_to_tokens(
        tokens=request.tokens,
        title=request.title,
        body=request.body,
        data=request.data
    )
    
    return NotificationResponse(
        success=True,
        message=f"Test notification sent to {len(request.tokens)} tokens",
        tokens_count=len(request.tokens),
        fcm_response=result
    )


@router.delete("/token", response_model=FCMTokenResponse)
async def remove_fcm_token(
    request: FCMTokenRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Remove FCM token for authenticated user
    
    Args:
        request: FCM token request containing the registration token to remove
        user_id: Firebase user ID from authentication
        
    Returns:
        Success response or error if token doesn't exist
    """
    firestore_service = FirestoreService()
    
    result = await firestore_service.remove_fcm_token(user_id, request.fcm_token)
    
    if not result['success']:
        if "does not exist" in result['message'] or "No FCM tokens found" in result['message']:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result['message']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['message']
            )
    
    return FCMTokenResponse(
        success=True,
        message=result['message']
    )