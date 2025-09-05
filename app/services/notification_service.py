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
            print(f"🔔 Preparing to send notification to {len(tokens)} tokens")
            print(f"📱 Title: {title}, Body: {body}")
            
            if not tokens or len(tokens) == 0:
                return {
                    "error": "No tokens provided",
                    "success_count": 0,
                    "failure_count": 0,
                    "total_tokens": 0
                }
            
            valid_tokens = [token for token in tokens if token and isinstance(token, str) and token.strip()]
            if len(valid_tokens) != len(tokens):
                print(f"⚠️ Filtered out {len(tokens) - len(valid_tokens)} invalid tokens")
            
            if not valid_tokens:
                return {
                    "error": "No valid tokens after filtering",
                    "success_count": 0,
                    "failure_count": len(tokens),
                    "total_tokens": len(tokens)
                }
            
            results = []
            success_count = 0
            failure_count = 0
            
            for i, token in enumerate(valid_tokens):
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=title,
                            body=body
                        ),
                        data={k: str(v) for k, v in (data or {}).items()},
                        token=token,
                        android=messaging.AndroidConfig(
                            notification=messaging.AndroidNotification(sound="default")
                        ),
                        apns=messaging.APNSConfig(
                            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
                        )
                    )
                    
                    message_id = messaging.send(message)
                    print(f"✅ Token {i+1}/{len(valid_tokens)}: Success - {message_id}")
                    
                    results.append({
                        "token_index": i,
                        "success": True,
                        "message_id": message_id
                    })
                    success_count += 1
                    
                except Exception as token_error:
                    error_msg = str(token_error)
                    print(f"❌ Token {i+1}/{len(valid_tokens)}: Failed - {error_msg}")
                    print(f"🔍 Token details: {token[:20]}...{token[-10:]} (length: {len(token)})")
                    
                    if "APNS" in error_msg:
                        print("💡 This appears to be an iOS token. Possible issues:")
                        print("   - Bundle ID mismatch (app vs Firebase Console)")
                        print("   - Missing Push Notifications capability in Xcode")
                        print("   - App ID not configured in Apple Developer Console")
                        print("   - APNs authentication key issues")
                        print("   - Development vs Production environment mismatch")
                    elif "Web Push" in error_msg:
                        print("💡 This appears to be a web token. Check Web Push certificates.")
                    elif "not found" in error_msg or "invalid" in error_msg:
                        print("💡 Token may be expired, invalid, or from wrong project.")                                                        
                    results.append({
                        "token_index": i,
                        "success": False,
                        "error": error_msg,
                        "token_preview": f"{token[:20]}...{token[-10:]}"
                    })
                    failure_count += 1
            
            print(f"📊 Notification results: {success_count} success, {failure_count} failed out of {len(valid_tokens)} tokens")
            
            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "total_tokens": len(tokens),
                "valid_tokens": len(valid_tokens),
                "responses": results
            }
            
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