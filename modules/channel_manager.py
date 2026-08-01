import re
import logging
from config import DEFAULT_REGULAR_CHANNEL_ID, DEFAULT_CLONE_CHANNEL_ID
from database import db

logger = logging.getLogger(__name__)

class ChannelManager:
    """Manage bot channels for uploads."""
    
    def __init__(self, bot):
        self.bot = bot
        self.regular_channel = self._load_channel("regular_channel", DEFAULT_REGULAR_CHANNEL_ID)
        self.clone_channel = self._load_channel("clone_channel", DEFAULT_CLONE_CHANNEL_ID)
    
    def _load_channel(self, key: str, default: int) -> int:
        """Load channel ID from database or use default."""
        try:
            stored = db.get_setting(key)
            if stored:
                return int(stored)
        except Exception as e:
            logger.warning(f"Error loading {key}: {e}")
        return default
    
    def get_regular_channel(self) -> int:
        """Get regular download channel ID."""
        return self.regular_channel
    
    def get_clone_channel(self) -> int:
        """Get TikTok clone channel ID."""
        return self.clone_channel
    
    def set_regular_channel(self, channel_id: int | str) -> bool:
        """Set regular download channel. Returns True if successful."""
        try:
            # Verify channel access first
            is_accessible, msg = self.verify_channel_access(channel_id)
            if not is_accessible:
                logger.error(f"Cannot access channel: {msg}")
                return False
            
            # Convert to int if string
            if isinstance(channel_id, str):
                if channel_id.startswith("@"):
                    # Keep @name format but convert to ID after verification
                    pass
                else:
                    channel_id = int(channel_id)
            
            self.regular_channel = channel_id
            db.set_setting("regular_channel", str(channel_id))
            logger.info(f"✅ Regular channel set to {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting regular channel: {e}")
            return False
    
    def set_clone_channel(self, channel_id: int | str) -> bool:
        """Set TikTok clone channel. Returns True if successful."""
        try:
            # Verify channel access first
            is_accessible, msg = self.verify_channel_access(channel_id)
            if not is_accessible:
                logger.error(f"Cannot access channel: {msg}")
                return False
            
            # Convert to int if string
            if isinstance(channel_id, str):
                if channel_id.startswith("@"):
                    # Keep @name format but convert to ID after verification
                    pass
                else:
                    channel_id = int(channel_id)
            
            self.clone_channel = channel_id
            db.set_setting("clone_channel", str(channel_id))
            logger.info(f"✅ Clone channel set to {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting clone channel: {e}")
            return False
    
    def extract_channel_id(self, text: str) -> str | None:
        """Extract channel ID from text (URL or @name)."""
        text = text.strip()
        
        # Handle @channel_name format
        if text.startswith("@"):
            return text
        
        # Handle URL format (t.me/channel_name or t.me/c/123456789)
        match = re.search(r"(?:t\.me|telegram\.me)(?:/c)?/([a-zA-Z0-9_-]+|\d+)", text)
        if match:
            return match.group(1)
        
        # Handle direct channel ID
        if text.lstrip("-").isdigit():
            return text
        
        return None
    
    def verify_channel_access(self, channel_id: str | int) -> tuple[bool, str]:
        """Verify bot has access to channel."""
        try:
            # Try to get channel info
            chat = self.bot.get_chat(channel_id)
            logger.info(f"✅ Verified access to channel: {chat.title} ({channel_id})")
            return True, f"✅ تم التحقق من القناة: {chat.title}"
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Cannot access channel {channel_id}: {error_msg}")
            
            if "not a member" in error_msg.lower():
                return False, "❌ البوت ليس عضو في هذه القناة. أضف البوت للقناة أولاً!"
            elif "chat not found" in error_msg.lower() or "not found" in error_msg.lower():
                return False, "❌ القناة غير موجودة. تأكد من الاسم أو الرابط"
            elif "forbidden" in error_msg.lower():
                return False, "❌ البوت ليس له صلاحيات كافية في هذه القناة"
            else:
                return False, f"❌ خطأ في الوصول للقناة: {error_msg}"
