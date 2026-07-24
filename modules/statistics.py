import logging
from database import db

logger = logging.getLogger(__name__)

class Statistics:
    """Handle statistics collection and reporting."""
    
    @staticmethod
    def record_regular_download(user_id: int, platform: str, url: str) -> None:
        """Record a regular download."""
        try:
            db.record_action(user_id, "regular_download", platform, url)
            logger.info(f"Recorded download: user={user_id}, platform={platform}")
        except Exception as e:
            logger.error(f"Error recording download: {e}")
    
    @staticmethod
    def record_tiktok_clone(user_id: int, account_url: str, video_count: int) -> None:
        """Record TikTok cloning activity."""
        try:
            db.record_action(user_id, "tiktok_clone", "tiktok", str(video_count))
            logger.info(f"Recorded clone: user={user_id}, videos={video_count}")
        except Exception as e:
            logger.error(f"Error recording clone: {e}")
    
    @staticmethod
    def get_report() -> str:
        """Generate statistics report."""
        try:
            stats = db.get_statistics()
            
            report = (
                "📊 <b>تقرير الإحصائيات</b>\n\n"
                f"👥 <b>المستخدمون:</b>\n"
                f"• إجمالي: {stats['total_users']}\n"
                f"• نشطون: {stats['active_users']}\n"
                f"• محظورون: {stats['blocked_users']}\n\n"
                f"📥 <b>التحميلات:</b>\n"
                f"• تحميلات عادية: {stats['regular_downloads']}\n"
                f"• استنساخ TikTok: {stats['tiktok_clones']}\n"
                f"• إجمالي الفيديوهات: {stats['total_videos']}"
            )
            
            return report
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return "❌ خطأ في جلب الإحصائيات"
