"""
Manga chapter tracking and notification service
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from google.cloud import firestore

from app.services.firebase_service import FirestoreService, get_firestore_client
from app.services.notification_service import NotificationService
from app.services.zenrows_service import zenrows_service
import requests


class MangaTrackerService:
    """Tracks manga chapters and handles notification scheduling"""
    
    def __init__(self):
        self.firestore_service = FirestoreService()
        self.notification_service = NotificationService()
        self.db = get_firestore_client()
        self.api_base_url = "https://api.comick.fun/comic"
    
    async def check_all_manga_chapters(self) -> Dict[str, Any]:
        """
        Check all tracked manga for new chapters
        
        Returns:
            Summary of the check operation
        """
        print("🔍 Starting manga chapter check...")
        start_time = datetime.utcnow()
        
        try:
            await self._update_cron_status("chapter_checker", "running")
            
            tracked_manga = await self._get_tracked_manga()
            print(f"📚 Found {len(tracked_manga)} manga to check")
            
            results = {
                "total_manga_checked": len(tracked_manga),
                "manga_with_new_chapters": 0,
                "total_new_chapters": 0,
                "errors": []
            }
            
            for i, manga_data in enumerate(tracked_manga):
                try:
                    manga_hid = manga_data["manga_hid"]
                    
                    if i > 0:
                        import random
                        delay = random.uniform(3, 7)
                        print(f"⏳ Waiting {delay:.1f} seconds before next API call...")
                        await asyncio.sleep(delay)
                    
                    new_chapters = await self._check_manga_chapters(manga_hid, manga_data)
                    
                    if new_chapters:
                        results["manga_with_new_chapters"] += 1
                        results["total_new_chapters"] += len(new_chapters)
                        print(f"📖 {manga_hid}: Found {len(new_chapters)} new chapters")
                    
                except Exception as e:
                    error_msg = f"Error checking manga {manga_data.get('manga_hid', 'unknown')}: {str(e)}"
                    print(f"❌ {error_msg}")
                    results["errors"].append(error_msg)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._update_cron_status("chapter_checker", "completed", duration)
            
            print(f"✅ Chapter check completed in {duration:.1f}s")
            return results
            
        except Exception as e:
            await self._update_cron_status("chapter_checker", "failed", error=str(e))
            raise e
    
    async def _get_tracked_manga(self) -> List[Dict[str, Any]]:
        """Get all manga that need to be tracked from user subscriptions"""
        try:
            subscription_docs = self.db.collection('subscriptions').stream()
            
            manga_hids = set()
            for doc in subscription_docs:
                data = doc.to_dict()
                user_hids = data.get('manga_hids', [])
                manga_hids.update(user_hids)
            
            print(f"📚 Found {len(manga_hids)} unique manga from user subscriptions")
            
            tracked_manga = []
            for manga_hid in manga_hids:
                tracking_data = await self._get_or_create_tracking_data(manga_hid)
                if tracking_data:
                    tracked_manga.append(tracking_data)
            
            return tracked_manga
            
        except Exception as e:
            print(f"❌ Error getting tracked manga: {e}")
            return []
    
    async def _get_or_create_tracking_data(self, manga_hid: str) -> Dict[str, Any]:
        """Get existing tracking data or create new one"""
        try:
            doc_ref = self.db.collection('manga_trackings').document(manga_hid)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['manga_hid'] = manga_hid
                return data
            else:
                print(f"🆕 Creating new tracking for manga {manga_hid}")
                await self.initialize_manga_tracking(manga_hid)
                
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    data['manga_hid'] = manga_hid
                    return data
                
            return None
            
        except Exception as e:
            print(f"❌ Error getting tracking data for {manga_hid}: {e}")
            return None
    
    async def _check_manga_chapters(self, manga_hid: str, manga_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check a specific manga for new chapters
        
        Args:
            manga_hid: Manga hid identifier
            manga_data: Current tracking data for the manga
            
        Returns:
            List of new chapters found
        """
        try:
            chapters = await self._fetch_manga_chapters(manga_hid)
            if not chapters:
                print(f"⚠️  API unavailable for {manga_hid} (likely Cloudflare protection)")
                print(f"📝 Keeping existing tracking data and will retry later")
                return []
            
            last_created_at = manga_data.get('last_created_at')
            already_notified = set(manga_data.get('already_notified_chapters', []))
            
            new_chapters = []
            latest_created_at = last_created_at
            
            for chapter in chapters:
                chapter_created_at = chapter.get('created_at')
                chapter_num = str(chapter.get('chap', ''))
                
                if not chapter_num or chapter_num in already_notified:
                    continue
                
                if not last_created_at or chapter_created_at > last_created_at:
                    new_chapters.append({
                        "id": chapter.get('id'),
                        "chap": chapter_num,
                        "title": chapter.get('title'),
                        "created_at": chapter_created_at,
                        "group_name": chapter.get('group_name', []),
                        "detected_at": datetime.utcnow().isoformat() + 'Z'
                    })
                    
                    if not latest_created_at or chapter_created_at > latest_created_at:
                        latest_created_at = chapter_created_at
            
            if new_chapters:
                await self._update_manga_tracking(manga_hid, latest_created_at)
                await self._store_pending_notifications(manga_hid, new_chapters)
            
            return new_chapters
            
        except Exception as e:
            print(f"❌ Error checking chapters for {manga_hid}: {e}")
            return []
    
    async def _fetch_manga_chapters(self, manga_hid: str) -> List[Dict[str, Any]]:
        """Fetch chapters from the manga API using ZenRows bypass"""
        print(f"🔍 Fetching chapters for {manga_hid}")
        
        try:
            print("🌐 Attempting ZenRows Cloudflare bypass...")
            data = await zenrows_service.fetch_manga_chapters(manga_hid)
            
            if data and 'chapters' in data:
                chapters = data.get('chapters', [])
                print(f"✅ Successfully fetched {len(chapters)} chapters for {manga_hid} via ZenRows")
                return chapters
            
            print("🔄 ZenRows failed, trying direct request...")
            return await self._fetch_direct(manga_hid)
                        
        except Exception as e:
            print(f"❌ Error fetching chapters for {manga_hid}: {e}")
            return []
    
    async def _fetch_direct(self, manga_hid: str) -> List[Dict[str, Any]]:
        """Direct fetch as fallback"""
        url = f"{self.api_base_url}/{manga_hid}/chapters?date-order=2&lang=en"
        
        try:
            import http.client
            import ssl
            import json
            from urllib.parse import urlparse
            
            print("🔄 Using direct http.client request...")
            
            parsed_url = urlparse(url)
            host = parsed_url.netloc
            path = parsed_url.path + '?' + parsed_url.query
            
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, context=context)
            
            conn.request("GET", path)
            response = conn.getresponse()
            
            if response.status == 200:
                response_data = response.read().decode('utf-8')
                data = json.loads(response_data)
                chapters = data.get('chapters', [])
                print(f"✅ Direct request successful! Fetched {len(chapters)} chapters for {manga_hid}")
                conn.close()
                return chapters
            else:
                print(f"❌ Direct request failed for {manga_hid}: {response.status}")
                
                if response.status == 403:
                    print("💡 403 Forbidden - Cloudflare protection active")
                    print("   🔧 Configure ZenRows in .env:")
                    print("     ZENROWS_API_KEY=<your_zenrows_api_key>")
                    print("   📖 Get your API key at: https://www.zenrows.com/")
                
                conn.close()
                return []
                        
        except Exception as e:
            print(f"❌ Direct request error: {e}")
            return []
    
    async def _get_manga_title(self, manga_id: str) -> str:
        """Get manga title from API"""
        try:
            manga_url = f"https://api.comick.fun/comic/{manga_id}"
            
            params = {
                'url': manga_url,
                'apikey': zenrows_service.api_key,
                'js_render': 'false',
                'premium_proxy': 'true',
            }
            
            if zenrows_service.api_key:
                response = requests.get(zenrows_service.base_url, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    title = data.get('comic', {}).get('title', f'Manga {manga_id}')
                    return title
            
            return f"Manga {manga_id}"
            
        except Exception as e:
            print(f"❌ Error fetching manga title for {manga_id}: {e}")
            return f"Manga {manga_id}"
    
    async def _update_manga_tracking(self, manga_hid: str, latest_created_at: str):
        """Update manga tracking data"""
        try:
            doc_ref = self.db.collection('manga_trackings').document(manga_hid)
            doc_ref.update({
                'last_created_at': latest_created_at,
                'last_checked_at': datetime.utcnow().isoformat() + 'Z',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
        except Exception as e:
            print(f"❌ Error updating tracking for {manga_hid}: {e}")
    
    async def _store_pending_notifications(self, manga_hid: str, new_chapters: List[Dict[str, Any]]):
        """Store new chapters for pending notifications"""
        try:
            doc_ref = self.db.collection('pending_notifications').document(manga_hid)
            doc = doc_ref.get()
            
            if doc.exists:
                existing_data = doc.to_dict()
                existing_chapters = existing_data.get('chapters', [])
                
                existing_chap_nums = {ch.get('chap') for ch in existing_chapters}
                for chapter in new_chapters:
                    if chapter.get('chap') not in existing_chap_nums:
                        existing_chapters.append(chapter)
                
                doc_ref.update({
                    'chapters': existing_chapters,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            else:
                doc_ref.set({
                    'manga_hid': manga_hid,
                    'chapters': new_chapters,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                
        except Exception as e:
            print(f"❌ Error storing pending notifications for {manga_hid}: {e}")
    
    async def send_scheduled_notifications(self, day: str = None) -> Dict[str, Any]:
        """
        Send notifications for all pending chapters
        
        Args:
            day: "wednesday" or "saturday", auto-detected if None
            
        Returns:
            Summary of notification sending
        """
        if not day:
            day = "wednesday" if datetime.utcnow().weekday() == 2 else "saturday"
        
        print(f"📢 Starting {day} notification batch...")
        start_time = datetime.utcnow()
        
        try:
            pending_docs = self.db.collection('pending_notifications').stream()
            
            results = {
                "day": day,
                "total_manga_processed": 0,
                "total_notifications_sent": 0,
                "total_success": 0,
                "total_failures": 0,
                "manga_notifications": []
            }
            
            for doc in pending_docs:
                manga_hid = doc.id
                data = doc.to_dict()
                chapters = data.get('chapters', [])
                
                if not chapters:
                    continue
                
                manga_result = await self._send_manga_notifications(manga_hid, chapters)
                results["manga_notifications"].append(manga_result)
                results["total_manga_processed"] += 1
                results["total_notifications_sent"] += manga_result["subscribers_count"]
                results["total_success"] += manga_result["success_count"]
                results["total_failures"] += manga_result["failure_count"]
                
                await self._mark_chapters_notified(manga_hid, chapters)
                
                doc.reference.delete()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            await self._log_notification_history(day, results, duration)
            
            print(f"✅ Notification batch completed in {duration:.1f}s")
            return results
            
        except Exception as e:
            print(f"❌ Error in notification batch: {e}")
            raise e
    
    async def _send_manga_notifications(self, manga_hid: str, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send notifications for a specific manga's chapters"""
        try:
            subscribers = await self.firestore_service.get_manga_subscribers(manga_hid)
            
            if not subscribers:
                return {
                    "manga_hid": manga_hid,
                    "chapters_sent": [ch.get('chap') for ch in chapters],
                    "subscribers_count": 0,
                    "success_count": 0,
                    "failure_count": 0
                }
            
            chapter_titles = []
            for ch in chapters:
                chapter_title = ch.get('title', '').strip()
                if chapter_title:
                    chapter_titles.append(chapter_title)
            
            manga_title = await self.firestore_service.get_manga_title_by_hid(manga_hid)
            
            title = "📖 New Chapter 📖"
            
            if len(chapters) == 1:
                if chapter_titles:
                    body = f"A new chapter has arrived: • {manga_title} • {chapter_titles[0]}"
                else:
                    body = f"A new chapter has arrived: • {manga_title} •"
            else:
                if chapter_titles:
                    chapter_list = " • ".join(chapter_titles)
                    body = f"New chapters have arrived: • {manga_title} • {chapter_list}"
                else:
                    chapter_numbers = ", ".join([f"Ch. {ch.get('chap')}" for ch in chapters])
                    body = f"New chapters have arrived: • {manga_title} • Chapters {chapter_numbers}"
            
            result = await self.notification_service.send_manga_notification(
                manga_id=manga_hid,
                title=title,
                body=body,
                data={
                    "type": "new_chapters",
                    "manga_hid": manga_hid,
                    "manga_title": manga_title,
                    "chapter_count": str(len(chapters)),
                    "chapters": chapter_list,
                    "latest_chapter": chapters[0].get('chap') if chapters else "",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return {
                "manga_hid": manga_hid,
                "chapters_sent": [ch.get('chap') for ch in chapters],
                "subscribers_count": len(subscribers),
                "success_count": result.get("success_count", 0),
                "failure_count": result.get("failure_count", 0)
            }
            
        except Exception as e:
            print(f"❌ Error sending notifications for {manga_hid}: {e}")
            return {
                "manga_hid": manga_hid,
                "chapters_sent": [ch.get('chap') for ch in chapters],
                "subscribers_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "error": str(e)
            }
    
    async def _mark_chapters_notified(self, manga_hid: str, chapters: List[Dict[str, Any]]):
        """Mark chapters as already notified"""
        try:
            chapter_nums = [str(ch.get('chap')) for ch in chapters if ch.get('chap')]
            
            doc_ref = self.db.collection('manga_trackings').document(manga_hid)
            doc_ref.update({
                'already_notified_chapters': firestore.ArrayUnion(chapter_nums),
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
        except Exception as e:
            print(f"❌ Error marking chapters notified for {manga_hid}: {e}")
    
    async def _log_notification_history(self, day: str, results: Dict[str, Any], duration: float):
        """Log notification batch to history"""
        try:
            history_id = f"notif_{datetime.utcnow().strftime('%Y%m%d')}_{day}"
            
            doc_ref = self.db.collection('notification_histories').document(history_id)
            doc_ref.set({
                "id": history_id,
                "sent_at": firestore.SERVER_TIMESTAMP,
                "type": "scheduled",
                "day": day,
                "manga_notifications": results["manga_notifications"],
                "total_manga_processed": results["total_manga_processed"],
                "total_notifications_sent": results["total_notifications_sent"],
                "total_success": results["total_success"],
                "total_failures": results["total_failures"],
                "processing_time_seconds": duration
            })
            
        except Exception as e:
            print(f"❌ Error logging notification history: {e}")
    
    async def _update_cron_status(self, job_name: str, status: str, duration: float = None, error: str = None):
        """Update cron job status"""
        try:
            doc_ref = self.db.collection('cron_jobs').document(job_name)
            
            update_data = {
                'status': status,
                'last_run': firestore.SERVER_TIMESTAMP
            }
            
            if status == "completed" and duration:
                update_data['average_duration_seconds'] = duration
                update_data['run_count'] = firestore.Increment(1)
                update_data['last_error'] = None
            elif status == "failed" and error:
                update_data['last_error'] = error
            
            doc_ref.set(update_data, merge=True)
            
        except Exception as e:
            print(f"❌ Error updating cron status: {e}")
    
    async def initialize_manga_tracking(self, manga_hid: str) -> bool:
        """
        Initialize tracking for a new manga
        
        Args:
            manga_hid: Manga hid identifier
            
        Returns:
            True if successful
        """
        try:
            doc_ref = self.db.collection('manga_trackings').document(manga_hid)
            doc = doc_ref.get()
            
            if not doc.exists:
                chapters = await self._fetch_manga_chapters(manga_hid)
                
                latest_created_at = None
                existing_chapters = []
                
                if chapters:
                    for chapter in chapters:
                        chapter_created_at = chapter.get('created_at')
                        if not latest_created_at or chapter_created_at > latest_created_at:
                            latest_created_at = chapter_created_at
                        
                        chapter_num = str(chapter.get('chap', ''))
                        if chapter_num:
                            existing_chapters.append(chapter_num)
                
                doc_ref.set({
                    'manga_hid': manga_hid,
                    'last_checked_at': datetime.utcnow().isoformat() + 'Z',
                    'last_created_at': latest_created_at,
                    'already_notified_chapters': existing_chapters,
                    'is_active': True,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                
                print(f"✅ Initialized tracking for manga {manga_hid}")
            else:
                doc_ref.update({
                    'is_active': True,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            return True
            
        except Exception as e:
            print(f"❌ Error initializing manga tracking for {manga_hid}: {e}")
            return False
    