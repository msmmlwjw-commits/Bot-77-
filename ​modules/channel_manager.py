import logging
import telebot
from database import db
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class ChannelManager:
    """Manage channel settings and validation."""
    
    REGULAR_CHANNEL_KEY = "regular_channel_id"
    CLONE_CHANNEL_KEY = "clone_channel_id"
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
    
    def extract_channel_id(self, channel_input: str) -> Optional[str]:
        """Extract channel ID from URL or username.
        
        Args:
            channel_input: Channel URL (like https://t.me/mychannel) or @username
        
        Returns:
            Channel ID or None
        """
        if channel_input.startswith("@"):
            return channel_input
        
        if "t.me/" in channel_input:
            parts = channel_input.split("/")
            return "@" + parts[-1] if parts[-1] else None
        
        return None
    
    def verify_channel_access(self, channel_id: str) -> Tuple[bool, str]:
        """Verify that bot is admin in the channel.
        
        Args:
            channel_id: Channel identifier (@name or numeric ID)
        
        Returns:
            (is_admin, message)
        """
        try:
            member = self.bot.get_chat_member(channel_id, self.bot.get_me().id)
            
            if member.status in ['administrator', 'creator']:
                return True, "✅ تم التحقق بنجاح من صلاحيات البوت في القناة"
            else:
                return False, "❌ البوت ليس مشرفاً في هذه القناة. يجب أن يكون البوت مشرفاً لإرسال الرسائل."
        except Exception as e:
            logger.error(f"Error verifying channel access: {e}")
            return False, f"❌ خطأ في التحقق: {str(e)}"
    
    def set_regular_channel(self, channel_id: str) -> bool:
        """Set regular download channel."""
        try:
            db.set_setting(self.REGULAR_CHANNEL_KEY, channel_id)
            logger.info(f"Regular channel set to: {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting regular channel: {e}")
            return False
    
    def set_clone_channel(self, channel_id: str) -> bool:
        """Set TikTok clone channel."""
        try:
            db.set_setting(self.CLONE_CHANNEL_KEY, channel_id)
            logger.info(f"Clone channel set to: {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting clone channel: {e}")
            return False
    
    def get_regular_channel(self) -> str:
        """Get regular download channel ID."""
        return db.get_setting(self.REGULAR_CHANNEL_KEY) or str(-1003872259900)
    
    def get_clone_channel(self) -> str:
        """Get TikTok clone channel ID."""
        return db.get_setting(self.CLONE_CHANNEL_KEY) or str(-1003872259900)
