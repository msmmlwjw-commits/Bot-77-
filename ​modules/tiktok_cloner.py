import os
import re
import json
import time
import tempfile
import logging
import asyncio
import urllib.request
import telebot
import yt_dlp
from typing import Optional, Dict
from database import db
from modules.channel_manager import ChannelManager

logger = logging.getLogger(__name__)

class TikTokCloner:
    """Handle TikTok account cloning functionality."""
    
    def __init__(self, bot: telebot.TeleBot, channel_manager: ChannelManager):
        self.bot = bot
        self.channel_manager = channel_manager
        self.user_sessions = {}  # user_id -> session_data
    
    def parse_tiktok_input(self, text: str) -> Optional[str]:
        """Parse TikTok input and return account URL.
        
        Accepts:
        - https://www.tiktok.com/@username
        - @username
        - username
        
        Returns:
            Full TikTok URL or None
        """
        text = text.strip()
        
        # Already a full URL
        if text.startswith("http"):
            if "tiktok.com" in text:
                return text
            return None
        
        # @username format
        if text.startswith("@"):
            username = text[1:]
            return f"https://www.tiktok.com/@{username}"
        
        # Just username
        if re.match(r"^[a-zA-Z0-9._-]+$", text):
            return f"https://www.tiktok.com/@{text}"
        
        return None
    
    def start_clone_session(self, user_id: int, account_url: str) -> Dict:
        """Start a new TikTok clone session.
        
        Returns:
            Session data
        """
        username = self._extract_username_from_url(account_url)
        session_id = db.create_tiktok_session(user_id, account_url, username)
        
        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'account_url': account_url,
            'username': username,
            'last_video_index': 0,
            'is_downloading': False,
            'is_cancelled': False
        }
        
        self.user_sessions[user_id] = session_data
        logger.info(f"Started TikTok clone session for user {user_id}: {username}")
        
        return session_data
    
    def get_user_session(self, user_id: int) -> Optional[Dict]:
        """Get user's active TikTok session."""
        return self.user_sessions.get(user_id)
    
    def clear_user_session(self, user_id: int) -> None:
        """Clear user's session."""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
    
    def change_account(self, user_id: int) -> None:
        """Change account for user session."""
        self.clear_user_session(user_id)
        logger.info(f"Account changed for user {user_id}")
    
    def _extract_username_from_url(self, url: str) -> str:
        """Extract username from TikTok URL."""
        match = re.search(r'@([a-zA-Z0-9._-]+)', url)
        return match.group(1) if match else "unknown"
    
    def _get_tiktok_videos(self, account_url: str, start_index: int = 0, 
                          batch_size: int = 20) -> Optional[list]:
        """Get TikTok videos using yt-dlp.
        
        Returns:
            List of video info or None
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(account_url, download=False)
            
            if 'entries' not in info:
                return None
            
            entries = info['entries']
            return entries[start_index:start_index + batch_size]
        
        except Exception as e:
            logger.error(f"Error fetching TikTok videos: {e}")
            return None
    
    def _download_tiktok_video(self, video_url: str, tmpdir: str) -> Optional[str]:
        """Download a single TikTok video.
        
        Returns:
            Path to downloaded video or None
        """
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]',
                'outtmpl': os.path.join(tmpdir, 'video.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 3,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            # Find the downloaded file
            for f in os.listdir(tmpdir):
                if f.startswith('video.'):
                    return os.path.join(tmpdir, f)
            
            return None
        
        except Exception as e:
            logger.error(f"Error downloading TikTok video: {e}")
            return None
