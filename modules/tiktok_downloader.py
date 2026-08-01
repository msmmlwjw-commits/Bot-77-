import os
import logging
import tempfile
import yt_dlp
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class TikTokDownloader:
    """Handle TikTok video downloads with proper audio support."""
    
    BASE_YDL_OPTS = {
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
        "retries": 3,
        "cookiefile": None,
    }
    
    DOWNLOAD_PROFILES = [
        {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "postprocessor_args": ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k"],
            "ffmpeg_location": None,
            "extractor_args": {"tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}},
        },
        {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "postprocessor_args": ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k"],
            "ffmpeg_location": None,
            "extractor_args": {"tiktok": {"api_hostname": ["api19-normal-c-useast1a.tiktokv.com"]}},
        },
        {
            "format": "best",
            "merge_output_format": "mp4",
            "extractor_args": {"tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}},
        },
    ]
    
    MAX_RETRIES = 5
    RETRY_DELAY = 2
    
    @staticmethod
    def download_tiktok_video(url: str, output_path: str, user_agent: str, is_long: bool = False) -> Optional[str]:
        """Download a single TikTok video with guaranteed audio."""
        last_exc = None
        total_attempts = TikTokDownloader.MAX_RETRIES * len(TikTokDownloader.DOWNLOAD_PROFILES)
        attempt_num = 0
        
        for retry in range(TikTokDownloader.MAX_RETRIES):
            for profile in TikTokDownloader.DOWNLOAD_PROFILES:
                attempt_num += 1
                opts = {**TikTokDownloader.BASE_YDL_OPTS, **profile}
                opts["outtmpl"] = os.path.join(output_path, "video.%(ext)s")
                opts["http_headers"] = {"User-Agent": user_agent}
                
                logger.info(f"⏳ محاولة {attempt_num}/{total_attempts} — {url}")
                
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                    
                    logger.info(f"✅ نجح التحميل في المحاولة {attempt_num}")
                    return TikTokDownloader.find_downloaded_file(output_path)
                
                except Exception as exc:
                    last_exc = exc
                    logger.warning(f"❌ فشلت المحاولة {attempt_num}/{total_attempts}")
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
            logger.error(f"Error finding file: {e}")
        return None
    
    @staticmethod
    def get_account_videos(account_url: str, start_index: int = 0, limit: int = 20) -> List[Dict]:
        """Get videos from a TikTok account."""
        try:
            opts = {
                "quiet": False,
                "no_warnings": False,
                "socket_timeout": 30,
                "extract_flat": "in_playlist",
                "playlistend": start_index + limit,
                "playliststart": start_index + 1,
            }
            
            logger.info(f"🔍 جاري جلب {limit} فيديو من {account_url}")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(account_url, download=False)
            
            if info and "entries" in info:
                entries = info["entries"]
                logger.info(f"✅ تم العثور على {len(entries)} فيديو")
                return entries
            
            return []
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return []
