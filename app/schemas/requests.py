"""
Pydantic schemas for request models
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class FCMTokenRequest(BaseModel):
    """Request model for saving FCM token"""

    fcm_token: str = Field(..., description="FCM registration token", min_length=1)


class MangaSubscriptionRequest(BaseModel):
    """Request model for manga subscription/unsubscription"""

    manga_id: str = Field(..., description="Manga identifier", min_length=1)


class NotificationRequest(BaseModel):
    """Request model for sending notifications"""

    manga_id: str = Field(..., description="Manga identifier", min_length=1)
    title: str = Field(
        ..., description="Notification title", min_length=1, max_length=100
    )
    body: str = Field(
        ..., description="Notification body", min_length=1, max_length=500
    )
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")


class TestNotificationRequest(BaseModel):
    """Request model for sending test notifications to specific tokens"""

    tokens: list[str] = Field(..., description="List of FCM tokens", min_items=1)
    title: str = Field(
        ..., description="Notification title", min_length=1, max_length=100
    )
    body: str = Field(
        ..., description="Notification body", min_length=1, max_length=500
    )
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")
