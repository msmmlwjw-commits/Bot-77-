import logging
import os
import tempfile
import time
import yt_dlp
from typing import Optional, List, Dict
from modules.audio_fixer import AudioFixer

logger = logging.getLogger(__name__)

class TikTokDownloader:
    """Handle TikTok video downloading with audio fix."""
    
    DOWNLOAD_TIMEOUT = 60  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    @staticmethod
    def download_tiktok_video(url: str, tmpdir: str, user_agent: str) -> Optional[str]:
        """Download TikTok video with proper audio handling.
        
        Args:
            url: TikTok video URL
            tmpdir: Temporary directory for download
            user_agent: User agent string
        
        Returns:
            Path to downloaded video file or None
        """
        ydl_opts = {
            'format': 'best[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(tmpdir, 'video.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': TikTokDownloader.DOWNLOAD_TIMEOUT,
            'retries': TikTokDownloader.MAX_RETRIES,
            'http_headers': {'User-Agent': user_agent},
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'prefixes': None,
                'format': 'mp4',
            }],
        }
        
        for attempt in range(TikTokDownloader.MAX_RETRIES):
            try:
                logger.info(f"Downloading TikTok video (attempt {attempt + 1}/{TikTokDownloader.MAX_RETRIES}): {url}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                
                # Find downloaded file
                downloaded_file = None
                for f in os.listdir(tmpdir):
                    if f.startswith('video.'):
                        downloaded_file = os.path.join(tmpdir, f)
                        break
                
                if not downloaded_file:
                    logger.error("Downloaded file not found")
                    continue
                
                # Check and fix audio
                if not AudioFixer.check_audio(downloaded_file):
                    logger.warning("Video has no audio, attempting to fix...")
                    
                    # Try to fix using FFmpeg
                    fixed_file = os.path.join(tmpdir, 'video_fixed.mp4')
                    if AudioFixer.fix_silent_video(downloaded_file, fixed_file):
                        os.remove(downloaded_file)
                        downloaded_file = fixed_file
                    else:
                        logger.warning("Could not fix audio, sending video as is")
                
                logger.info(f"Successfully downloaded TikTok video: {downloaded_file}")
                return downloaded_file
            
            except Exception as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                if attempt < TikTokDownloader.MAX_RETRIES - 1:
                    time.sleep(TikTokDownloader.RETRY_DELAY)
        
        logger.error("Failed to download TikTok video after all retries")
        return None
    
    @staticmethod
    def get_account_videos(account_url: str, start_index: int = 0, batch_size: int = 20) -> Optional[List[Dict]]:
        """Get list of videos from TikTok account.
        
        Args:
            account_url: TikTok account URL
            start_index: Start from this video index
            batch_size: Number of videos to fetch
        
        Returns:
            List of video info dicts or None
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'socket_timeout': 30,
            }
            
            logger.info(f"Fetching TikTok videos from {account_url} (index: {start_index}, batch: {batch_size})")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(account_url, download=False)
            
            if 'entries' not in info:
                logger.error("No entries found in TikTok account")
                return None
            
            entries = info['entries']
            batch = entries[start_index:start_index + batch_size]
            
            logger.info(f"Fetched {len(batch)} videos")
            return batch if batch else None
        
        except Exception as e:
            logger.error(f"Error fetching TikTok videos: {e}")
            return None
