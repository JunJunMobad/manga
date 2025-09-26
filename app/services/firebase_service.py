"""
Firebase Admin SDK service for authentication and Firestore operations
"""

import firebase_admin
from firebase_admin import credentials, auth, firestore
from google.cloud.firestore_v1 import Client as FirestoreClient
from typing import Optional, Dict, Any

from app.config import settings


firebase_app: Optional[firebase_admin.App] = None
db: Optional[FirestoreClient] = None


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global firebase_app, db

    if firebase_app is None:
        try:
            print("🔥 Initializing Firebase Admin SDK...")

            cred_dict = settings.get_firebase_credentials()
            print(
                f"✅ Firebase credentials loaded for project: {cred_dict.get('project_id')}"
            )

            cred = credentials.Certificate(cred_dict)
            firebase_app = firebase_admin.initialize_app(cred)
            print(f"✅ Firebase Admin SDK initialized successfully")

            db = firestore.client()
            print(f"✅ Firestore client connected successfully")

        except Exception as e:
            print(f"❌ Failed to initialize Firebase: {str(e)}")
            raise e
    else:
        print("🔥 Firebase already initialized")


def get_firestore_client() -> FirestoreClient:
    """Get Firestore client instance"""
    if db is None:
        raise RuntimeError(
            "Firebase not initialized. Call initialize_firebase() first."
        )
    return db


async def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    """
    Verify Firebase ID token and return decoded token

    Args:
        id_token: Firebase ID token from client

    Returns:
        Decoded token containing user information

    Raises:
        ValueError: If token is invalid
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        raise ValueError(f"Invalid token: {str(e)}")


class FirestoreService:
    """Handles Firebase authentication and Firestore database operations"""

    def __init__(self):
        self.db = get_firestore_client()

    async def save_fcm_token(self, user_id: str, fcm_token: str) -> dict:
        """
        Save or update FCM token for user (adds to existing tokens, removes duplicates)

        Args:
            user_id: Firebase user ID
            fcm_token: FCM registration token

        Returns:
            Dict with 'success' boolean and 'message' string
        """
        try:
            doc_ref = self.db.collection("fcm_tokens").document(user_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                current_tokens = data.get("tokens", [])

                if fcm_token in current_tokens:
                    print(f"⚠️ FCM token already exists for user {user_id}")
                    return {"success": False, "message": "This token is already stored"}

            doc_ref.set(
                {
                    "tokens": firestore.ArrayUnion([fcm_token]),
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )

            print(f"✅ FCM token saved for user {user_id}")
            return {"success": True, "message": "FCM token saved successfully"}

        except Exception as e:
            print(f"❌ Error saving FCM token: {e}")
            return {"success": False, "message": f"Error saving FCM token: {str(e)}"}

    async def get_fcm_tokens(self, user_id: str) -> list:
        """Get FCM tokens for user"""
        try:
            doc_ref = self.db.collection("fcm_tokens").document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("tokens", [])
            return []
        except Exception as e:
            print(f"❌ Error getting FCM tokens: {e}")
            return []

    async def remove_fcm_token(self, user_id: str, fcm_token: str) -> dict:
        """
        Remove a specific FCM token for user (useful for cleaning up invalid tokens)

        Args:
            user_id: Firebase user ID
            fcm_token: FCM registration token to remove

        Returns:
            Dict with 'success' boolean and 'message' string
        """
        try:
            doc_ref = self.db.collection("fcm_tokens").document(user_id)
            doc = doc_ref.get()

            if not doc.exists:
                print(f"❌ No FCM tokens document found for user {user_id}")
                return {"success": False, "message": "No FCM tokens found for user"}

            data = doc.to_dict()
            current_tokens = data.get("tokens", [])

            if fcm_token not in current_tokens:
                print(f"❌ FCM token not found in user {user_id} tokens")
                return {"success": False, "message": "FCM token does not exist"}

            doc_ref.set(
                {
                    "tokens": firestore.ArrayRemove([fcm_token]),
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )

            print(f"✅ FCM token removed for user {user_id}")
            return {"success": True, "message": "FCM token removed successfully"}

        except Exception as e:
            print(f"❌ Error removing FCM token: {e}")
            return {"success": False, "message": f"Error removing FCM token: {str(e)}"}

    async def get_or_create_manga_info(self, manga_id: str) -> dict:
        """
        Get manga info from Firestore or fetch from API if not exists

        Args:
            manga_id: Manga identifier

        Returns:
            Dict with manga info including hid and title
        """
        try:
            manga_ref = self.db.collection("mangas").document(manga_id)
            manga_doc = manga_ref.get()

            if manga_doc.exists:
                manga_data = manga_doc.to_dict()
                print(f"✅ Found existing manga info for {manga_id}")
                return {
                    "success": True,
                    "manga_id": manga_id,
                    "hid": manga_data.get("hid"),
                    "title": manga_data.get("title"),
                    "data": manga_data,
                }

            print(f"🔍 Fetching manga info for {manga_id} from API...")
            manga_info = await self._fetch_manga_info_from_api(manga_id)

            if not manga_info:
                return {
                    "success": False,
                    "message": f"Could not fetch manga info for {manga_id}",
                }

            manga_data = {
                "id": manga_id,
                "hid": manga_info["hid"],
                "title": manga_info["title"],
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

            manga_ref.set(manga_data)
            print(f"✅ Stored new manga info for {manga_id}: {manga_info['title']}")

            return {
                "success": True,
                "manga_id": manga_id,
                "hid": manga_info["hid"],
                "title": manga_info["title"],
                "data": manga_data,
            }

        except Exception as e:
            print(f"❌ Error getting manga info for {manga_id}: {e}")
            return {"success": False, "message": f"Error getting manga info: {str(e)}"}

    async def _fetch_manga_info_from_api(self, manga_id: str) -> dict:
        """Fetch manga info from API using ZenRows"""
        try:
            from app.services.zenrows_service import zenrows_service

            manga_info = await zenrows_service.fetch_manga_info(manga_id)

            if manga_info:
                return {
                    "hid": manga_info["hid"],
                    "title": manga_info["title"],
                    "full_data": manga_info.get("full_data", {}),
                }
            else:
                print(f"❌ Could not fetch manga info for {manga_id}")
                return None

        except Exception as e:
            print(f"❌ Error fetching manga info from API: {e}")
            return None

    async def subscribe_to_manga(self, user_id: str, manga_id: str) -> dict:
        """
        Subscribe user to manga notifications

        Args:
            user_id: Firebase user ID
            manga_id: Manga identifier

        Returns:
            Dict with 'success' boolean and 'message' string
        """
        try:
            manga_info = await self.get_or_create_manga_info(manga_id)

            if not manga_info["success"]:
                return {
                    "success": False,
                    "message": f'Could not get manga info: {manga_info.get("message", "Unknown error")}',
                }

            hid = manga_info["hid"]
            title = manga_info["title"]

            doc_ref = self.db.collection("subscriptions").document(user_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                current_hids = data.get("manga_hids", [])

                if hid in current_hids:
                    print(
                        f"⚠️ User {user_id} already subscribed to manga {manga_id} (hid: {hid})"
                    )
                    return {
                        "success": False,
                        "message": f"You already subscribed to this manga: {title}",
                    }

            doc_ref.set(
                {
                    "manga_hids": firestore.ArrayUnion([hid]),
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )

            print(
                f"✅ User {user_id} subscribed to manga {title} (id: {manga_id}, hid: {hid})"
            )
            return {
                "success": True,
                "message": f"Successfully subscribed to manga: {title}",
                "manga_id": manga_id,
                "hid": hid,
                "title": title,
            }

        except Exception as e:
            print(f"❌ Error subscribing to manga: {e}")
            return {
                "success": False,
                "message": f"Error subscribing to manga: {str(e)}",
            }

    async def unsubscribe_from_manga(self, user_id: str, manga_id: str) -> dict:
        """
        Unsubscribe user from manga notifications

        Args:
            user_id: Firebase user ID
            manga_id: Manga identifier

        Returns:
            Dict with 'success' boolean and 'message' string
        """
        try:
            manga_info = await self.get_or_create_manga_info(manga_id)

            if not manga_info["success"]:
                return {
                    "success": False,
                    "message": f'Could not get manga info: {manga_info.get("message", "Unknown error")}',
                }

            hid = manga_info["hid"]
            title = manga_info["title"]

            doc_ref = self.db.collection("subscriptions").document(user_id)
            doc = doc_ref.get()

            if not doc.exists:
                print(f"❌ No subscriptions document found for user {user_id}")
                return {"success": False, "message": "User has no manga subscriptions"}

            data = doc.to_dict()
            current_hids = data.get("manga_hids", [])

            if hid not in current_hids:
                print(
                    f"❌ User {user_id} is not subscribed to manga {manga_id} (hid: {hid})"
                )
                return {
                    "success": False,
                    "message": f"User did not subscribe to this manga: {title}",
                }

            doc_ref.set(
                {
                    "manga_hids": firestore.ArrayRemove([hid]),
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )

            print(
                f"✅ User {user_id} unsubscribed from manga {title} (id: {manga_id}, hid: {hid})"
            )
            return {
                "success": True,
                "message": f"Successfully unsubscribed from manga: {title}",
                "manga_id": manga_id,
                "hid": hid,
                "title": title,
            }

        except Exception as e:
            print(f"❌ Error unsubscribing from manga: {e}")
            return {
                "success": False,
                "message": f"Error unsubscribing from manga: {str(e)}",
            }

    async def get_manga_subscribers(self, manga_hid: str) -> list:
        """
        Get all users subscribed to a specific manga

        Args:
            manga_hid: Manga hid identifier

        Returns:
            List of user IDs subscribed to the manga
        """
        try:
            subscribers = []
            docs = (
                self.db.collection("subscriptions")
                .where("manga_hids", "array_contains", manga_hid)
                .stream()
            )

            for doc in docs:
                subscribers.append(doc.id)

            return subscribers
        except Exception as e:
            print(f"Error getting manga subscribers: {e}")
            return []

    async def get_manga_title_by_hid(self, manga_hid: str) -> str:
        """
        Get manga title by hid

        Args:
            manga_hid: Manga hid identifier

        Returns:
            Manga title or fallback string
        """
        try:
            manga_docs = (
                self.db.collection("mangas")
                .where("hid", "==", manga_hid)
                .limit(1)
                .stream()
            )

            for doc in manga_docs:
                manga_data = doc.to_dict()
                return manga_data.get("title", f"Manga {manga_hid}")

            return f"Manga {manga_hid}"

        except Exception as e:
            print(f"❌ Error getting manga title by hid: {e}")
            return f"Manga {manga_hid}"

    async def get_user_subscriptions(self, user_id: str) -> list:
        """Get user's manga subscriptions"""
        try:
            doc_ref = self.db.collection("subscriptions").document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("mangas", [])
            return []
        except Exception as e:
            print(f"Error getting user subscriptions: {e}")
            return []
