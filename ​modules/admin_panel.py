import logging
import telebot
from database import db
from modules.channel_manager import ChannelManager
from typing import Callable

logger = logging.getLogger(__name__)

class AdminPanel:
    """Handle admin management panel."""
    
    # Admin panel states
    STATE_MAIN_MENU = "admin_main"
    STATE_EDIT_WELCOME = "admin_edit_welcome"
    STATE_SET_REGULAR_CHANNEL = "admin_set_regular_channel"
    STATE_SET_CLONE_CHANNEL = "admin_set_clone_channel"
    STATE_BROADCAST_TYPE = "admin_broadcast_type"
    STATE_BROADCAST_CONTENT = "admin_broadcast_content"
    STATE_BROADCAST_CAPTION = "admin_broadcast_caption"
    STATE_BROADCAST_CONFIRM = "admin_broadcast_confirm"
    
    def __init__(self, bot: telebot.TeleBot, admin_id: int, channel_manager: ChannelManager):
        self.bot = bot
        self.admin_id = admin_id
        self.channel_manager = channel_manager
        self.admin_states = {}  # admin_id -> current_state
        self.broadcast_data = {}  # admin_id -> broadcast_data
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id == self.admin_id
    
    def build_main_menu_keyboard(self) -> telebot.types.InlineKeyboardMarkup:
        """Build admin main menu keyboard."""
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("✏️ تعديل رسالة الترحيب", 
                                                     callback_data="admin_edit_welcome"))
        markup.add(telebot.types.InlineKeyboardButton("📢 قناة التحميل العادي", 
                                                     callback_data="admin_regular_channel"))
        markup.add(telebot.types.InlineKeyboardButton("🎬 قناة الاستنساخ", 
                                                     callback_data="admin_clone_channel"))
        markup.add(telebot.types.InlineKeyboardButton("📡 إذاعة للجميع", 
                                                     callback_data="admin_broadcast"))
        markup.add(telebot.types.InlineKeyboardButton("📊 الإحصائيات", 
                                                     callback_data="admin_stats"))
        markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", 
                                                     callback_data="go_back"))
        return markup
    
    def build_back_keyboard(self) -> telebot.types.InlineKeyboardMarkup:
        """Build back button keyboard."""
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_back"))
        return markup
    
    def get_welcome_message(self) -> str:
        """Get current welcome message."""
        return db.get_setting("welcome_message") or self._get_default_welcome()
    
    def set_welcome_message(self, message: str) -> bool:
        """Set welcome message."""
        try:
            db.set_setting("welcome_message", message)
            logger.info("Welcome message updated")
            return True
        except Exception as e:
            logger.error(f"Error setting welcome message: {e}")
            return False
    
    def _get_default_welcome(self) -> str:
        return (
            "أهلاً بك في بوت تحميل من السوشيال ميديا! 🌹\n\n"
            "بـوتـنـا سـهـل الاسـتـخـدام..\n"
            "كـل مـا عـلـيـك فـعـلـه هـو إرسـال الـرابط أو إعـادة تـوجـيـهـه إلـيـنـا.\n\n"
            "يـمـكـنـك الـتـحـمـيـل مـن:\n"
            "• تـيـك تـوك\n"
            "• إنـسـتـغـرام\n"
            "• فـيـسـبـوك\n"
            "• بـيـنـتـرسـت\n\n"
            "شـكـراً لـكـم! ✨"
        )
