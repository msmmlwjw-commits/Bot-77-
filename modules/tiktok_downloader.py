import os
import logging
import tempfile
import yt_dlp
from typing import Optional, List, Dict, Tuple

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
    
    # Profile لتحميل الصوت منفصل (الموسيقى)
    AUDIO_ONLY_PROFILE = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "postprocessor_args": ["-c:a", "aac", "-b:a", "128k"],
        "extractor_args": {"tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}},
    }
    
    MAX_RETRIES = 5
    RETRY_DELAY = 2
    
    @staticmethod
    def check_video_has_audio(file_path: str) -> bool:
        """Check if downloaded video has audio stream."""
        try:
            opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(file_path, download=False)
                # Check if video has audio
                return info.get('acodec') != 'none' if 'acodec' in info else True
        except:
            return True  # Assume has audio if check fails
    
    @staticmethod
    def download_tiktok_video(url: str, output_path: str, user_agent: str, is_long: bool = False) -> Optional[Dict]:
        """
        Download a single TikTok video with guaranteed audio or separate audio.
        Returns dict with:
        - video_path: path to video file
        - audio_path: path to audio file (or None if video has audio)
        - has_audio: boolean indicating if video has audio embedded
        """
        last_exc = None
        total_attempts = TikTokDownloader.MAX_RETRIES * len(TikTokDownloader.DOWNLOAD_PROFILES)
        attempt_num = 0
        video_file = None
        has_audio = False
        
        # Try to download video
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
                    
                    video_file = TikTokDownloader.find_downloaded_file(output_path)
                    if video_file:
                        # Check if has audio
                        has_audio = TikTokDownloader.check_video_has_audio(video_file)
                        logger.info(f"✅ تم التحميل! الفيديو يحتوي على صوت: {has_audio}")
                        break
                
                except Exception as exc:
                    last_exc = exc
                    logger.warning(f"❌ فشلت المحاولة {attempt_num}/{total_attempts}")
                    import time
                    if attempt_num < total_attempts:
                        time.sleep(TikTokDownloader.RETRY_DELAY)
            
            if video_file:
                break
        
        if not video_file:
            if last_exc:
                raise last_exc
            return None
        
        audio_file = None
        
        # إذا لم يكن هناك صوت، حمل الصوت منفصل
        if not has_audio:
            logger.warning("⚠️ الفيديو بدون صوت! جاري تحميل الصوت منفصل...")
            audio_file = TikTokDownloader._download_audio_only(url, output_path, user_agent)
            if audio_file:
                logger.info(f"✅ تم تحميل الصوت منفصل: {audio_file}")
        
        return {
            "video_path": video_file,
            "audio_path": audio_file,
            "has_audio": has_audio
        }
    
    @staticmethod
    def _download_audio_only(url: str, output_path: str, user_agent: str) -> Optional[str]:
        """Download audio only from TikTok."""
        try:
            opts = {**TikTokDownloader.BASE_YDL_OPTS, **TikTokDownloader.AUDIO_ONLY_PROFILE}
            opts["outtmpl"] = os.path.join(output_path, "audio.%(ext)s")
            opts["http_headers"] = {"User-Agent": user_agent}
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            
            matches = [f for f in os.listdir(output_path) if f.startswith("audio.")]
            if matches:
                return os.path.join(output_path, matches[0])
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل الصوت: {e}")
        
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
