import logging
from database import db

logger = logging.getLogger(__name__)

class Statistics:
    """Handle statistics and reporting."""
    
    @staticmethod
    def record_regular_download(user_id: int, platform: str, url: str) -> None:
        """Record a regular download action."""
        db.record_action(user_id, "regular_download", platform, url)
        logger.info(f"Recorded regular download for user {user_id} from {platform}")
    
    @staticmethod
    def record_tiktok_clone(user_id: int, account_url: str, video_count: int) -> None:
        """Record a TikTok clone action."""
        db.record_action(user_id, "tiktok_clone", "tiktok", str(video_count))
        logger.info(f"Recorded TikTok clone for user {user_id}: {video_count} videos")
    
    @staticmethod
    def get_report() -> str:
        """Generate statistics report."""
        stats = db.get_statistics()
        
        report = (
            "📊 <b>إحصائيات البوت:</b>\n\n"
            f"👥 إجمالي المستخدمين: {stats['total_users']}\n"
            f"✅ المستخدمون النشطون: {stats['active_users']}\n"
            f"🚫 المستخدمون المحظورون: {stats['blocked_users']}\n\n"
            f"📥 عمليات التحميل العادي: {stats['regular_downloads']}\n"
            f"🚀 عمليات استنساخ TikTok: {stats['tiktok_clones']}\n"
            f"🎬 إجمالي الفيديوهات: {stats['total_videos']}"
        )
        
        return report
