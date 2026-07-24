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
    
    def set_regular_channel(self, channel_id: int) -> None:
        """Set regular download channel."""
        self.regular_channel = channel_id
        db.set_setting("regular_channel", str(channel_id))
        logger.info(f"Regular channel set to {channel_id}")
    
    def set_clone_channel(self, channel_id: int) -> None:
        """Set TikTok clone channel."""
        self.clone_channel = channel_id
        db.set_setting("clone_channel", str(channel_id))
        logger.info(f"Clone channel set to {channel_id}")
    
    def extract_channel_id(self, text: str) -> int | None:
        """Extract channel ID from text (URL or @name)."""
        # Handle @channel_name format
        if text.startswith("@"):
            return text
        
        # Handle URL format (t.me/channel_name or t.me/c/123456789)
        match = re.search(r"(?:t\.me|telegram\.me)(?:/c)?/([a-zA-Z0-9_-]+|\d+)", text)
        if match:
            return match.group(1)
        
        # Handle direct channel ID
        if text.lstrip("-").isdigit():
            return int(text)
        
        return None
    
    def verify_channel_access(self, channel_id: int | str) -> tuple[bool, str]:
        """Verify bot has access to channel."""
        try:
            # Try to get channel info
            chat = self.bot.get_chat(channel_id)
            return True, f"✅ تم التحقق من القناة: {chat.title}"
        except Exception as e:
            return False, f"❌ لا يمكن الوصول للقناة: {str(e)}"
