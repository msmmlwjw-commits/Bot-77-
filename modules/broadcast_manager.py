import logging
import telebot
from typing import Dict, Optional
from database import db

logger = logging.getLogger(__name__)

class BroadcastManager:
    """Manage broadcast operations."""
    
    def __init__(self, bot):
        self.bot = bot
        self.broadcasts: Dict[int, Dict] = {}
    
    def start_broadcast(self, admin_id: int, content_type: str) -> None:
        """Start a new broadcast session."""
        self.broadcasts[admin_id] = {
            "content_type": content_type,
            "content": None,
            "caption": None,
        }
        logger.info(f"Started broadcast session for admin {admin_id}: {content_type}")
    
    def set_broadcast_content(self, admin_id: int, message: telebot.types.Message) -> bool:
        """Set broadcast content from user message."""
        try:
            if admin_id not in self.broadcasts:
                return False
            
            broadcast = self.broadcasts[admin_id]
            content_type = broadcast["content_type"]
            
            # Store message details based on content type
            if content_type == "text":
                broadcast["content"] = message.text
            elif content_type == "photo":
                broadcast["content"] = message.photo[-1].file_id
            elif content_type == "video":
                broadcast["content"] = message.video.file_id
            elif content_type == "audio":
                broadcast["content"] = message.audio.file_id
            elif content_type == "document":
                broadcast["content"] = message.document.file_id
            elif content_type == "sticker":
                broadcast["content"] = message.sticker.file_id
            
            broadcast["caption"] = message.caption or ""
            logger.info(f"Broadcast content set for admin {admin_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting broadcast content: {e}")
            return False
    
    def get_broadcast_data(self, admin_id: int) -> Optional[Dict]:
        """Get broadcast data for admin."""
        return self.broadcasts.get(admin_id)
    
    def execute_broadcast(self, admin_id: int) -> Dict:
        """Execute broadcast to all active users."""
        try:
            if admin_id not in self.broadcasts:
                return {"successful": 0, "failed": 0, "blocked": 0, "total": 0}
            
            broadcast = self.broadcasts[admin_id]
            content_type = broadcast["content_type"]
            content = broadcast["content"]
            caption = broadcast.get("caption", "")
            
            # Get all active users
            active_users = db.get_all_active_users()
            
            successful = 0
            failed = 0
            blocked = 0
            
            for user_id in active_users:
                try:
                    # Send based on content type
                    if content_type == "text":
                        self.bot.send_message(user_id, content, parse_mode="HTML")
                    elif content_type == "photo":
                        self.bot.send_photo(user_id, content, caption=caption, parse_mode="HTML")
                    elif content_type == "video":
                        self.bot.send_video(user_id, content, caption=caption, parse_mode="HTML")
                    elif content_type == "audio":
                        self.bot.send_audio(user_id, content, caption=caption, parse_mode="HTML")
                    elif content_type == "document":
                        self.bot.send_document(user_id, content, caption=caption, parse_mode="HTML")
                    elif content_type == "sticker":
                        self.bot.send_sticker(user_id, content)
                    
                    successful += 1
                
                except telebot.apihelper.ApiTelegramException as e:
                    if e.error_code == 403:
                        blocked += 1
                        db.block_user(user_id)
                    else:
                        failed += 1
                        logger.warning(f"Failed to send to {user_id}: {e}")
                
                except Exception as e:
                    failed += 1
                    logger.warning(f"Error sending to {user_id}: {e}")
            
            # Record broadcast
            db.record_broadcast(admin_id, content_type, "", caption, len(active_users))
            
            result = {
                "successful": successful,
                "failed": failed,
                "blocked": blocked,
                "total": len(active_users)
            }
            
            logger.info(f"Broadcast executed: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error executing broadcast: {e}")
            return {"successful": 0, "failed": 0, "blocked": 0, "total": 0}
    
    def cancel_broadcast(self, admin_id: int) -> None:
        """Cancel broadcast session."""
        if admin_id in self.broadcasts:
            del self.broadcasts[admin_id]
            logger.info(f"Broadcast cancelled for admin {admin_id}")
