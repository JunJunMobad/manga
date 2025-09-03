"""
FCM notification service for sending push notifications using Firebase Admin SDK
"""
import json
from typing import List, Dict, Any
from firebase_admin import messaging
from app.config import settings
from app.services.firebase_service import FirestoreService


class NotificationService:
    """Service for sending FCM notifications"""
    
    def __init__(self):
        self.firestore_service = FirestoreService()
        print("✅ FCM notification service initialized with Firebase Admin SDK")
    
    async def send_notification_to_tokens(
        self, 
        tokens: List[str], 
        title: str, 
        body: str, 
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send notification to specific FCM tokens using Firebase Admin SDK
        
        Args:
            tokens: List of FCM registration tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            Response from FCM service
        """
        try:
            notification = messaging.Notification(
                title=title,
                body=body
            )
            
            android_config = messaging.AndroidConfig(
                notification=messaging.AndroidNotification(
                    sound="default"
                )
            )
            
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default")
                )
            )
            
            string_data = {}
            if data:
                string_data = {k: str(v) for k, v in data.items()}
            
            message = messaging.MulticastMessage(
                notification=notification,
                data=string_data,
                tokens=tokens,
                android=android_config,
                apns=apns_config
            )
            
            response = messaging.send_multicast(message)
            
            print(f"✅ Sent notification to {len(tokens)} tokens. Success: {response.success_count}, Failed: {response.failure_count}")
            
            result = {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "total_tokens": len(tokens),
                "responses": []
            }
            
            for idx, resp in enumerate(response.responses):
                token_result = {
                    "token_index": idx,
                    "success": resp.success
                }
                if not resp.success:
                    token_result["error"] = str(resp.exception)
                result["responses"].append(token_result)
            
            return result
            
        except Exception as e:
            print(f"❌ Error sending notification: {e}")
            return {
                "error": str(e),
                "success_count": 0,
                "failure_count": len(tokens),
                "total_tokens": len(tokens)
            }
    
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
            "success_count": result.get("success_count", 0),
            "failure_count": result.get("failure_count", 0),
            "fcm_response": result
        }