import logging
import os
import tempfile
import telebot
from typing import Optional, Dict, List
from database import db

logger = logging.getLogger(__name__)

class BroadcastManager:
    """Handle broadcast operations to all users."""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.broadcast_data = {}  # user_id -> broadcast_info
    
    def start_broadcast(self, admin_id: int, content_type: str) -> None:
        """Start broadcast process.
        
        Args:
            admin_id: Admin's Telegram ID
            content_type: Type of content (text, photo, video, audio, document, sticker)
        """
        self.broadcast_data[admin_id] = {
            'content_type': content_type,
            'content': None,
            'caption': None,
            'file_id': None,
        }
        logger.info(f"Started broadcast for admin {admin_id}, type: {content_type}")
    
    def set_broadcast_content(self, admin_id: int, message: telebot.types.Message) -> bool:
        """Set broadcast content from user message.
        
        Returns:
            True if content was set, False otherwise
        """
        if admin_id not in self.broadcast_data:
            return False
        
        broadcast = self.broadcast_data[admin_id]
        content_type = broadcast['content_type']
        
        try:
            if content_type == 'text':
                broadcast['content'] = message.text
            
            elif content_type == 'photo':
                if not message.photo:
                    return False
                broadcast['file_id'] = message.photo[-1].file_id
                broadcast['content'] = message.caption or ""
            
            elif content_type == 'video':
                if not message.video:
                    return False
                broadcast['file_id'] = message.video.file_id
                broadcast['content'] = message.caption or ""
            
            elif content_type == 'audio':
                if not message.audio:
                    return False
                broadcast['file_id'] = message.audio.file_id
                broadcast['content'] = message.caption or ""
            
            elif content_type == 'document':
                if not message.document:
                    return False
                broadcast['file_id'] = message.document.file_id
                broadcast['content'] = message.caption or ""
            
            elif content_type == 'sticker':
                if not message.sticker:
                    return False
                broadcast['file_id'] = message.sticker.file_id
            
            logger.info(f"Broadcast content set for admin {admin_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting broadcast content: {e}")
            return False
    
    def get_broadcast_data(self, admin_id: int) -> Optional[Dict]:
        """Get current broadcast data."""
        return self.broadcast_data.get(admin_id)
    
    def execute_broadcast(self, admin_id: int) -> Dict:
        """Execute broadcast to all active users.
        
        Returns:
            Dictionary with results (successful, failed, blocked)
        """
        if admin_id not in self.broadcast_data:
            return {}
        
        broadcast = self.broadcast_data[admin_id]
        content_type = broadcast['content_type']
        file_id = broadcast.get('file_id')
        content = broadcast.get('content', '')
        
        # Get all active users
        users = db.get_all_active_users()
        
        results = {
            'successful': 0,
            'failed': 0,
            'blocked': 0,
            'total': len(users)
        }
        
        # Record broadcast
        broadcast_id = db.record_broadcast(
            admin_id, content_type, file_id or content[:50],
            content[:100] if content_type == 'text' else content,
            len(users)
        )
        
        logger.info(f"Starting broadcast {broadcast_id} to {len(users)} users")
        
        for user_id in users:
            try:
                if content_type == 'text':
                    self.bot.send_message(
                        user_id, content,
                        parse_mode="HTML" if '<' in content else None
                    )
                
                elif content_type == 'photo':
                    self.bot.send_photo(user_id, file_id, caption=content, parse_mode="HTML" if '<' in content else None)
                
                elif content_type == 'video':
                    self.bot.send_video(user_id, file_id, caption=content, parse_mode="HTML" if '<' in content else None)
                
                elif content_type == 'audio':
                    self.bot.send_audio(user_id, file_id, caption=content, parse_mode="HTML" if '<' in content else None)
                
                elif content_type == 'document':
                    self.bot.send_document(user_id, file_id, caption=content, parse_mode="HTML" if '<' in content else None)
                
                elif content_type == 'sticker':
                    self.bot.send_sticker(user_id, file_id)
                
                results['successful'] += 1
            
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 403:
                    results['blocked'] += 1
                    db.block_user(user_id)
                else:
                    results['failed'] += 1
            
            except Exception as e:
                logger.warning(f"Error sending broadcast to user {user_id}: {e}")
                results['failed'] += 1
        
        # Update broadcast results
        db.update_broadcast_results(
            broadcast_id,
            results['successful'],
            results['failed'],
            results['blocked']
        )
        
        logger.info(f"Broadcast {broadcast_id} completed: {results['successful']} successful, {results['failed']} failed, {results['blocked']} blocked")
        
        # Clear broadcast data
        del self.broadcast_data[admin_id]
        
        return results
    
    def cancel_broadcast(self, admin_id: int) -> bool:
        """Cancel ongoing broadcast."""
        if admin_id in self.broadcast_data:
            del self.broadcast_data[admin_id]
            logger.info(f"Broadcast cancelled for admin {admin_id}")
            return True
        return False
