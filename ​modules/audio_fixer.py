import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AudioFixer:
    """Fix audio issues in downloaded videos."""
    
    @staticmethod
    def check_audio(video_path: str) -> bool:
        """Check if video has audio stream.
        
        Returns:
            True if audio exists, False otherwise
        """
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                 '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', video_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return 'audio' in result.stdout.lower()
        except Exception as e:
            logger.error(f"Error checking audio: {e}")
            return False
    
    @staticmethod
    def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
        """Merge separate video and audio streams using FFmpeg.
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Path to output file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                '-y',  # Overwrite output file
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Successfully merged audio and video: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg merge failed: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg merge timeout")
            return False
        except Exception as e:
            logger.error(f"Error merging audio: {e}")
            return False
    
    @staticmethod
    def fix_silent_video(video_path: str, output_path: str) -> bool:
        """Re-encode video to ensure audio is properly included.
        
        Args:
            video_path: Path to input video
            output_path: Path to output video
        
        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Successfully fixed silent video: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg fix failed: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg fix timeout")
            return False
        except Exception as e:
            logger.error(f"Error fixing silent video: {e}")
            return False
