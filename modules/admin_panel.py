import logging
import telebot
from database import db

logger = logging.getLogger(__name__)

class AdminPanel:
    """Handle admin panel operations."""
    
    def __init__(self, bot, admin_id: int, channel_manager):
        self.bot = bot
        self.admin_id = admin_id
        self.channel_manager = channel_manager
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id == self.admin_id
    
    def build_main_menu_keyboard(self) -> telebot.types.InlineKeyboardMarkup:
        """Build admin main menu keyboard."""
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("✏️ تعديل رسالة الترحيب", callback_data="admin_edit_welcome"))
        markup.add(telebot.types.InlineKeyboardButton("📢 قناة التحميل العادي", callback_data="admin_regular_channel"))
        markup.add(telebot.types.InlineKeyboardButton("🎬 قناة الاستنساخ", callback_data="admin_clone_channel"))
        markup.add(telebot.types.InlineKeyboardButton("📡 إرسال إذاعة", callback_data="admin_broadcast"))
        markup.add(telebot.types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"))
        markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="go_back"))
        return markup
    
    def get_welcome_message(self) -> str:
        """Get current welcome message."""
        custom_msg = db.get_setting("welcome_message")
        if custom_msg:
            return custom_msg
        
        return (
            "أهلاً بك في بوت تحميل من السوشيال ميديا! 🌹\n"
            "كل ما عليك فعله هو إرسال الرابط أو إعادة توجيهه إلينا."
        )
    
    def set_welcome_message(self, message: str) -> bool:
        """Set new welcome message."""
        try:
            db.set_setting("welcome_message", message)
            logger.info("Welcome message updated")
            return True
        except Exception as e:
            logger.error(f"Error setting welcome message: {e}")
            return False
