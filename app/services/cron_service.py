"""
Cron job service for scheduling background tasks
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any
import schedule
import threading


class CronService:
    """Manages background job scheduling and execution"""

    def __init__(self):
        self.manga_tracker = None
        self.is_running = False
        self.scheduler_thread = None

    def _get_manga_tracker(self):
        """Lazy initialization of manga tracker"""
        if self.manga_tracker is None:
            from app.services.manga_tracker_service import MangaTrackerService

            self.manga_tracker = MangaTrackerService()
        return self.manga_tracker

    def start_scheduler(self):
        """Start the background scheduler"""
        if self.is_running:
            print("⚠️ Scheduler is already running")
            return

        print("🕐 Starting cron scheduler...")

        schedule.every(12).hours.do(self._run_chapter_check)

        schedule.every().wednesday.at("18:00").do(self._run_wednesday_notifications)
        schedule.every().saturday.at("18:00").do(self._run_saturday_notifications)

        schedule.every().sunday.at("02:00").do(self._run_cleanup)

        self.is_running = True

        self.scheduler_thread = threading.Thread(
            target=self._run_scheduler, daemon=True
        )
        self.scheduler_thread.start()

        schedule.every(2).minutes.do(self._run_initial_chapter_check).tag("initial")

        print("✅ Cron scheduler started successfully")
        print("📅 Scheduled tasks:")
        print("   - Initial chapter check: In 2 minutes")
        print("   - Chapter check: Every 12 hours")
        print("   - Notifications: Wednesday & Saturday at 6 PM")
        print("   - Cleanup: Sunday at 2 AM")

    def stop_scheduler(self):
        """Stop the background scheduler"""
        if not self.is_running:
            print("⚠️ Scheduler is not running")
            return

        print("🛑 Stopping cron scheduler...")
        self.is_running = False
        schedule.clear()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)

        print("✅ Cron scheduler stopped")

    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                time.sleep(60)

    def _run_initial_chapter_check(self):
        """Run initial chapter check after startup - clears all data first"""
        try:
            print("🚀 Running initial chapter check after startup...")
            print("🧹 Clearing all existing tracking and notification data...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._clear_all_tracking_data())

            print("✅ All tracking data cleared, starting fresh chapter check...")
            self._run_chapter_check()

            schedule.clear("initial")
            print("✅ Initial chapter check completed, removed from schedule")

        except Exception as e:
            print(f"❌ Error in initial chapter check: {e}")

    async def _clear_all_tracking_data(self):
        """Clear all manga tracking and notification data from Firebase"""
        try:
            from app.services.firebase_service import get_firestore_client

            db = get_firestore_client()

            collections_to_clear = [
                "manga_trackings",
                "pending_notifications",
                "notification_histories",
                "cron_jobs",
            ]

            for collection_name in collections_to_clear:
                print(f"🗑️ Clearing {collection_name} collection...")

                docs = db.collection(collection_name).stream()

                deleted_count = 0
                for doc in docs:
                    doc.reference.delete()
                    deleted_count += 1

                print(f"✅ Deleted {deleted_count} documents from {collection_name}")

            print("🧹 All tracking and notification data cleared successfully!")

        except Exception as e:
            print(f"❌ Error clearing tracking data: {e}")
            raise e

    def _run_chapter_check(self):
        """Run manga chapter checking"""
        try:
            print("🔍 Running scheduled chapter check...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self._get_manga_tracker().check_all_manga_chapters()
            )

            print(f"📊 Chapter check results:")
            print(f"   - Manga checked: {result['total_manga_checked']}")
            print(f"   - Manga with new chapters: {result['manga_with_new_chapters']}")
            print(f"   - Total new chapters: {result['total_new_chapters']}")

            if result["errors"]:
                print(f"   - Errors: {len(result['errors'])}")

            loop.close()

        except Exception as e:
            print(f"❌ Error in scheduled chapter check: {e}")

    def _run_wednesday_notifications(self):
        """Run Wednesday notifications"""
        try:
            print("📢 Running Wednesday notifications...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self._get_manga_tracker().send_scheduled_notifications("wednesday")
            )

            self._log_notification_results("Wednesday", result)
            loop.close()

        except Exception as e:
            print(f"❌ Error in Wednesday notifications: {e}")

    def _run_saturday_notifications(self):
        """Run Saturday notifications"""
        try:
            print("📢 Running Saturday notifications...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self._get_manga_tracker().send_scheduled_notifications("saturday")
            )

            self._log_notification_results("Saturday", result)
            loop.close()

        except Exception as e:
            print(f"❌ Error in Saturday notifications: {e}")

    def _run_cleanup(self):
        """Run weekly cleanup tasks"""
        try:
            print("🧹 Running weekly cleanup...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Weekly maintenance tasks would go here

            print("✅ Weekly cleanup completed")
            loop.close()

        except Exception as e:
            print(f"❌ Error in weekly cleanup: {e}")

    def _log_notification_results(self, day: str, result: Dict[str, Any]):
        """Log notification results"""
        print(f"📊 {day} notification results:")
        print(f"   - Manga processed: {result['total_manga_processed']}")
        print(f"   - Notifications sent: {result['total_notifications_sent']}")
        print(f"   - Success: {result['total_success']}")
        print(f"   - Failures: {result['total_failures']}")

    async def trigger_chapter_check(self) -> Dict[str, Any]:
        """Manually trigger chapter check"""
        print("🔍 Manual chapter check triggered...")
        return await self._get_manga_tracker().check_all_manga_chapters()

    async def trigger_notifications(self, day: str = None) -> Dict[str, Any]:
        """Manually trigger notifications"""
        if not day:
            day = "wednesday" if datetime.now().weekday() == 2 else "saturday"

        print(f"📢 Manual {day} notifications triggered...")
        return await self._get_manga_tracker().send_scheduled_notifications(day)


cron_service = CronService()
