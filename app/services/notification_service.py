"""
FCM notification service for sending push notifications
"""
import requests
import json
from typing import List, Dict, Any
from app.config import settings
from app.services.firebase_service import FirestoreService


class NotificationService:
    """Service for sending FCM notifications"""
    
    def __init__(self):
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        self.firestore_service = FirestoreService()
        
        if not settings.fcm_server_key:
            print("⚠️  FCM_SERVER_KEY not configured. Notification sending will be disabled.")
    
    async def send_notification_to_tokens(
        self, 
        tokens: List[str], 
        title: str, 
        body: str, 
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send notification to specific FCM tokens
        
        Args:
            tokens: List of FCM registration tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            Response from FCM service
        """
        if not settings.fcm_server_key:
            return {
                "error": "FCM_SERVER_KEY not configured",
                "message": "Notification sending is disabled. Please configure FCM_SERVER_KEY environment variable."
            }
        
        headers = {
            "Authorization": f"key={settings.fcm_server_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "registration_ids": tokens,
            "notification": {
                "title": title,
                "body": body,
                "sound": "default"
            }
        }
        
        if data:
            payload["data"] = data
        
        try:
            response = requests.post(
                self.fcm_url,
                headers=headers,
                data=json.dumps(payload)
            )
            return response.json()
        except Exception as e:
            print(f"Error sending notification: {e}")
            return {"error": str(e)}
    
    async def send_manga_notification(
        self, 
        manga_id: str, 
        title: str, 
        body: str, 
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send notification to all users subscribed to a manga
        
        Args:
            manga_id: Manga identifier
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            Summary of notification sending results
        """
        subscribers = await self.firestore_service.get_manga_subscribers(manga_id)
        
        if not subscribers:
            return {"message": "No subscribers found for this manga", "sent_count": 0}
        
        all_tokens = []
        for user_id in subscribers:
            tokens = await self.firestore_service.get_fcm_tokens(user_id)
            all_tokens.extend(tokens)
        
        if not all_tokens:
            return {"message": "No FCM tokens found for subscribers", "sent_count": 0}
        
        notification_data = data or {}
        notification_data["manga_id"] = manga_id
        
        result = await self.send_notification_to_tokens(
            tokens=all_tokens,
            title=title,
            body=body,
            data=notification_data
        )
        
        return {
            "message": f"Notification sent to {len(all_tokens)} tokens",
            "subscribers_count": len(subscribers),
            "tokens_count": len(all_tokens),
            "fcm_response": result
        }