import logging
from typing import Optional, Dict
from database import db

logger = logging.getLogger(__name__)

class TikTokCloner:
    """Manage TikTok account cloning sessions."""
    
    def __init__(self, bot, channel_manager):
        self.bot = bot
        self.channel_manager = channel_manager
        self.user_sessions: Dict[int, Dict] = {}
    
    def start_clone_session(self, user_id: int, account_url: str) -> Dict:
        """
        Start a new TikTok clone session.
        
        Args:
            user_id: Telegram user ID
            account_url: TikTok account URL
        
        Returns:
            Session dictionary
        """
        # Extract username from URL
        username = account_url.split("@")[-1].rstrip("/")
        
        # Create session in database
        session_id = db.create_tiktok_session(user_id, account_url, username)
        
        # Store in memory
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "account_url": account_url,
            "username": username,
            "last_video_index": 0,
        }
        
        self.user_sessions[user_id] = session
        logger.info(f"Started clone session for user {user_id}: {username}")
        
        return session
    
    def get_user_session(self, user_id: int) -> Optional[Dict]:
        """Get active session for user."""
        if user_id in self.user_sessions:
            return self.user_sessions[user_id]
        
        # Try to load from database (most recent session)
        # Note: This is simplified - in production you'd query the DB
        return None
    
    def change_account(self, user_id: int) -> None:
        """Clear user's current session."""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        logger.info(f"Cleared session for user {user_id}")
    
    def update_session(self, user_id: int, session: Dict) -> None:
        """Update user session."""
        self.user_sessions[user_id] = session
