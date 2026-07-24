import json
import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

DB_FILE = "bot_database.db"

class BotDatabase:
    """Handle all database operations for the bot."""
    
    def __init__(self):
        self.db_file = DB_FILE
        self.init_db()
    
    def init_db(self):
        """Initialize database with required tables."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language_code TEXT,
                first_join TIMESTAMP,
                last_join TIMESTAMP,
                is_blocked INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT,
                platform TEXT,
                timestamp TIMESTAMP,
                details TEXT
            )
        """)
        
        # TikTok sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_url TEXT,
                username TEXT,
                last_video_index INTEGER DEFAULT 0,
                is_downloading INTEGER DEFAULT 0,
                is_cancelled INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        
        # Broadcasts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                content_type TEXT,
                content_path TEXT,
                caption TEXT,
                total_recipients INTEGER DEFAULT 0,
                successful INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                blocked INTEGER DEFAULT 0,
                timestamp TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def add_or_update_user(self, user_id: int, username: str, first_name: str, language_code: str) -> None:
        """Add or update user in database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,))
        
        if cursor.fetchone():
            cursor.execute("""
                UPDATE users SET last_join = ?, is_active = 1 WHERE user_id = ?
            """, (datetime.now(), user_id))
        else:
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, language_code, first_join, last_join, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (user_id, username, first_name, language_code, datetime.now(), datetime.now()))
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'language_code': row[3],
                'first_join': row[4],
                'last_join': row[5],
                'is_blocked': row[6],
                'is_active': row[7]
            }
        return None
    
    def block_user(self, user_id: int) -> None:
        """Mark user as blocked."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET is_blocked = 1, is_active = 0 WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        conn.close()
    
    def get_all_active_users(self) -> List[int]:
        """Get list of all active user IDs."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id FROM users WHERE is_active = 1 AND is_blocked = 0
        """)
        
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users
    
    def set_setting(self, key: str, value: str) -> None:
        """Set a configuration setting."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        """, (key, value))
        
        conn.commit()
        conn.close()
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get a configuration setting."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT value FROM settings WHERE key = ?
        """, (key,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def record_action(self, user_id: int, action_type: str, platform: str = "", details: str = "") -> None:
        """Record user action for statistics."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO statistics (user_id, action_type, platform, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, action_type, platform, datetime.now(), details))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """Get comprehensive statistics."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Active users
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1 AND is_blocked = 0")
        active_users = cursor.fetchone()[0]
        
        # Blocked users
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        blocked_users = cursor.fetchone()[0]
        
        # Regular downloads
        cursor.execute("SELECT COUNT(*) FROM statistics WHERE action_type = 'regular_download'")
        regular_downloads = cursor.fetchone()[0]
        
        # TikTok clones
        cursor.execute("SELECT COUNT(*) FROM statistics WHERE action_type = 'tiktok_clone'")
        tiktok_clones = cursor.fetchone()[0]
        
        # Total videos
        cursor.execute("SELECT SUM(CAST(details AS INTEGER)) FROM statistics WHERE details IS NOT NULL")
        total_videos = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'blocked_users': blocked_users,
            'regular_downloads': regular_downloads,
            'tiktok_clones': tiktok_clones,
            'total_videos': total_videos
        }
    
    def create_tiktok_session(self, user_id: int, account_url: str, username: str) -> int:
        """Create a new TikTok clone session."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tiktok_sessions (user_id, account_url, username, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, account_url, username, datetime.now(), datetime.now()))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def get_tiktok_session(self, session_id: int) -> Optional[Dict]:
        """Get TikTok session details."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM tiktok_sessions WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'session_id': row[0],
                'user_id': row[1],
                'account_url': row[2],
                'username': row[3],
                'last_video_index': row[4],
                'is_downloading': row[5],
                'is_cancelled': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        return None
    
    def update_tiktok_session(self, session_id: int, last_video_index: int = None, 
                            is_downloading: int = None, is_cancelled: int = None) -> None:
        """Update TikTok session."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if last_video_index is not None:
            updates.append("last_video_index = ?")
            params.append(last_video_index)
        
        if is_downloading is not None:
            updates.append("is_downloading = ?")
            params.append(is_downloading)
        
        if is_cancelled is not None:
            updates.append("is_cancelled = ?")
            params.append(is_cancelled)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now())
            params.append(session_id)
            
            query = f"UPDATE tiktok_sessions SET {', '.join(updates)} WHERE session_id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
    
    def record_broadcast(self, admin_id: int, content_type: str, content_path: str, 
                        caption: str, total_recipients: int) -> int:
        """Record a broadcast."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO broadcasts (admin_id, content_type, content_path, caption, total_recipients, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (admin_id, content_type, content_path, caption, total_recipients, datetime.now()))
        
        broadcast_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return broadcast_id
    
    def update_broadcast_results(self, broadcast_id: int, successful: int, 
                                failed: int, blocked: int) -> None:
        """Update broadcast results."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE broadcasts SET successful = ?, failed = ?, blocked = ? WHERE broadcast_id = ?
        """, (successful, failed, blocked, broadcast_id))
        
        conn.commit()
        conn.close()


db = BotDatabase()
