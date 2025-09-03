"""
Pydantic schemas for response models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class BaseResponse(BaseModel):
    """Base response model"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")


class FCMTokenResponse(BaseResponse):
    """Response model for FCM token operations"""
    pass


class MangaSubscriptionResponse(BaseResponse):
    """Response model for manga subscription operations"""
    manga_id: str = Field(..., description="Manga identifier")
    subscriptions: Optional[List[str]] = Field(None, description="User's current subscriptions")


class NotificationResponse(BaseResponse):
    """Response model for notification sending"""
    subscribers_count: Optional[int] = Field(None, description="Number of subscribers")
    tokens_count: Optional[int] = Field(None, description="Number of tokens notified")
    fcm_response: Optional[Dict[str, Any]] = Field(None, description="FCM service response")


class UserInfoResponse(BaseModel):
    """Response model for user information"""
    user_id: str = Field(..., description="Firebase user ID")
    subscriptions: List[str] = Field(default_factory=list, description="User's manga subscriptions")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service status")
    message: Optional[str] = Field(None, description="Additional information")