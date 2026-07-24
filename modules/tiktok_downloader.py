import os
import logging
import tempfile
import yt_dlp
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class TikTokDownloader:
    """Handle TikTok video downloads."""
    
    BASE_YDL_OPTS = {
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
        "retries": 3,
    }
    
    ATTEMPT_PROFILES = [
        {
            "format": "best[ext=mp4]/best",
            "extractor_args": {"tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}},
        },
        {
            "format": "best[ext=mp4]/best",
            "extractor_args": {"tiktok": {"api_hostname": ["api19-normal-c-useast1a.tiktokv.com"]}},
        },
    ]
    
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    
    @staticmethod
    def download_tiktok_video(url: str, output_path: str, user_agent: str) -> Optional[str]:
        """
        Download a single TikTok video.
        
        Args:
            url: TikTok video URL
            output_path: Directory to save video
            user_agent: User agent string
        
        Returns:
            Path to downloaded video file or None if failed
        """
        last_exc = None
        total_attempts = TikTokDownloader.MAX_RETRIES * len(TikTokDownloader.ATTEMPT_PROFILES)
        attempt_num = 0
        
        for retry in range(TikTokDownloader.MAX_RETRIES):
            for profile in TikTokDownloader.ATTEMPT_PROFILES:
                attempt_num += 1
                opts = {**TikTokDownloader.BASE_YDL_OPTS, **profile}
                opts["outtmpl"] = os.path.join(output_path, "video.%(ext)s")
                opts["http_headers"] = {"User-Agent": user_agent}
                
                logger.info(
                    f"Download attempt {attempt_num}/{total_attempts} (retry={retry}) — url={url}"
                )
                
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                    
                    logger.info(f"Download succeeded on attempt {attempt_num}")
                    
                    # Find and return the downloaded file
                    return TikTokDownloader.find_downloaded_file(output_path)
                
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        f"Attempt {attempt_num}/{total_attempts} failed: {exc}"
                    )
                    import time
                    if attempt_num < total_attempts:
                        time.sleep(TikTokDownloader.RETRY_DELAY)
        
        if last_exc:
            raise last_exc
        return None
    
    @staticmethod
    def find_downloaded_file(tmpdir: str) -> Optional[str]:
        """Find downloaded video file in directory."""
        try:
            matches = [f for f in os.listdir(tmpdir) if f.startswith("video.")]
            if matches:
                return os.path.join(tmpdir, matches[0])
        except Exception as e:
            logger.error(f"Error finding downloaded file: {e}")
        return None
    
    @staticmethod
    def get_account_videos(account_url: str, start_index: int = 0, limit: int = 20) -> List[Dict]:
        """
        Get videos from a TikTok account.
        
        Args:
            account_url: TikTok account URL (e.g., https://www.tiktok.com/@username)
            start_index: Starting index for pagination
            limit: Number of videos to fetch
        
        Returns:
            List of video info dictionaries
        """
        try:
            opts = {
                "quiet": False,
                "no_warnings": False,
                "socket_timeout": 30,
                "extract_flat": "in_playlist",
                "playlistend": start_index + limit,
                "playliststart": start_index + 1,
            }
            
            logger.info(f"Fetching TikTok account videos from {account_url} (start={start_index}, limit={limit})")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(account_url, download=False)
            
            if info and "entries" in info:
                entries = info["entries"]
                logger.info(f"Found {len(entries)} videos")
                return entries
            
            logger.warning("No videos found in account")
            return []
        
        except Exception as e:
            logger.error(f"Error fetching account videos: {e}")
            return []
