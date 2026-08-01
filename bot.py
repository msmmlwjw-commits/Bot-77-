import os
import re
import json
import time
import random
import tempfile
import logging
import traceback
import urllib.request
import threading
import telebot
import yt_dlp
from datetime import datetime
from typing import Optional, Dict, Tuple
from keep_alive import keep_alive
from database import db
from config import BOT_TOKEN, ADMIN_ID, TIKTOK_BATCH_SIZE
from modules.channel_manager import ChannelManager
from modules.tiktok_cloner import TikTokCloner
from modules.admin_panel import AdminPanel
from modules.statistics import Statistics
from modules.broadcast_manager import BroadcastManager
from modules.tiktok_downloader import TikTokDownloader

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)

channel_manager = ChannelManager(bot)
tiktok_cloner = TikTokCloner(bot, channel_manager)
admin_panel = AdminPanel(bot, ADMIN_ID, channel_manager)
broadcast_manager = BroadcastManager(bot)

blocked_users: set[int] = set()
seen_users: set[int] = set()
batch_mode_users: set[int] = set()
user_states: Dict[int, str] = {}
broadcast_data_store: Dict[int, Dict] = {}
tiktok_download_threads: Dict[int, threading.Thread] = {}
clone_cancellation: Dict[int, bool] = {}  # Track cancellation requests
progress_messages: Dict[int, Dict] = {}  # Track progress messages

def load_users_from_db():
    global seen_users, blocked_users
    try:
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error loading from database: {e}")

load_users_from_db()

SUPPORTED_PLATFORMS = {
    "tiktok":    re.compile(r"(https?://)?(www\.)?(vm\.|vt\.)?tiktok\.com/\S+", re.IGNORECASE),
    "instagram": re.compile(r"(https?://)?(www\.)?instagram\.com/\S+", re.IGNORECASE),
    "snapchat":  re.compile(r"(https?://)?(www\.)?snapchat\.com/\S+", re.IGNORECASE),
    "facebook":  re.compile(r"(https?://)?(www\.|m\.|fb\.)?(facebook\.com|fb\.watch)/\S+", re.IGNORECASE),
    "kwai":      re.compile(r"(https?://)?(www\.)?kwai\.(com|app)/\S+", re.IGNORECASE),
    "pinterest": re.compile(r"(https?://)?(www\.|pin\.)?pinterest\.(com|co\.\w+)/\S+", re.IGNORECASE),
}

PLATFORM_EMOJI = {
    "tiktok": "🎵", "instagram": "📸", "snapchat": "👻",
    "facebook": "📘", "kwai": "🎬", "pinterest": "📌",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15",
]

BASE_YDL_OPTS = {
    "merge_output_format": "mp4",
    "quiet": False,
    "no_warnings": False,
    "socket_timeout": 30,
    "retries": 3,
}

ATTEMPT_PROFILES = [
    {"format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "postprocessor_args": ["-c:v", "copy", "-c:a", "aac"]},
    {"format": "best[ext=mp4]/best"},
]

MAX_RETRIES = 3
RETRY_DELAY = 1

def notify_admin(text: str) -> None:
    try:
        bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to notify admin: %s", exc)

def send_to_user(chat_id: int, first_name: str, **kwargs) -> None:
    method = kwargs.pop("_method", "send_message")
    try:
        getattr(bot, method)(chat_id, **kwargs)
    except telebot.apihelper.ApiTelegramException as exc:
        if "Forbidden" in str(exc) or exc.error_code == 403:
            if chat_id not in blocked_users:
                blocked_users.add(chat_id)
                db.block_user(chat_id)
                logger.warning("User blocked the bot: %s", chat_id)
                notify_admin(f"🚫 مستخدم حظر البوت!\n👤 الاسم: {first_name}\n🆔 الآيدي: {chat_id}")
        else:
            raise

def resolve_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": random.choice(USER_AGENTS)})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.url
    except Exception:
        return url

def extract_video_url(text: str) -> Tuple[Optional[str], Optional[str]]:
    for platform, pattern in SUPPORTED_PLATFORMS.items():
        match = pattern.search(text)
        if match:
            return match.group(0), platform
    return None, None

def download_video(url: str, output_path: str, platform: str) -> dict:
    last_exc: Exception | None = None
    total_attempts = MAX_RETRIES * len(ATTEMPT_PROFILES)
    attempt_num = 0

    for retry in range(MAX_RETRIES):
        for profile in ATTEMPT_PROFILES:
            attempt_num += 1
            opts = {**BASE_YDL_OPTS, **profile}
            opts["outtmpl"] = output_path
            opts["http_headers"] = {"User-Agent": random.choice(USER_AGENTS)}
            logger.info(f"Download attempt {attempt_num}/{total_attempts} — {platform}")
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                logger.info("Download succeeded on attempt %d", attempt_num)
                return info
            except Exception as exc:
                last_exc = exc
                logger.warning(f"Attempt {attempt_num}/{total_attempts} failed: {exc}")
                if attempt_num < total_attempts:
                    time.sleep(RETRY_DELAY)
    raise last_exc

def find_downloaded_file(tmpdir: str) -> str:
    matches = [f for f in os.listdir(tmpdir) if f.startswith("video.")]
    if not matches:
        raise FileNotFoundError("Downloaded file not found")
    return os.path.join(tmpdir, matches[0])

def build_main_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📥 تحميل دفعة واحدة", callback_data="batch_download"))
    markup.add(telebot.types.InlineKeyboardButton("🚀 استنساخ TikTok", callback_data="tiktok_clone_start"))
    if admin_panel.is_admin(ADMIN_ID):
        markup.add(telebot.types.InlineKeyboardButton("⚙️ إدارة البوت", callback_data="admin_menu"))
    return markup

def build_back_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="go_back"))
    return markup

def build_tiktok_clone_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📥 جلب 20 فيديو", callback_data="tiktok_fetch_20"))
    markup.add(telebot.types.InlineKeyboardButton("🚀 استنساخ كامل", callback_data="tiktok_clone_full"))
    markup.add(telebot.types.InlineKeyboardButton("🔄 تغيير الحساب", callback_data="tiktok_change_account"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="go_back"))
    return markup

def build_continue_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ تكملة", callback_data="tiktok_continue"))
    markup.add(telebot.types.InlineKeyboardButton("❌ إيقاف", callback_data="tiktok_stop"))
    return markup

def build_clone_cancel_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("⛔ إلغاء الاستنساخ", callback_data="cancel_clone"))
    return markup

def build_broadcast_type_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📝 نص", callback_data="broadcast_text"))
    markup.add(telebot.types.InlineKeyboardButton("🖼️ صورة", callback_data="broadcast_photo"))
    markup.add(telebot.types.InlineKeyboardButton("🎬 فيديو", callback_data="broadcast_video"))
    markup.add(telebot.types.InlineKeyboardButton("🎵 صوت", callback_data="broadcast_audio"))
    markup.add(telebot.types.InlineKeyboardButton("📄 ملف", callback_data="broadcast_document"))
    markup.add(telebot.types.InlineKeyboardButton("😊 ملصق", callback_data="broadcast_sticker"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_back"))
    return markup

def build_broadcast_confirm_keyboard() -> telebot.types.InlineKeyboardMarkup:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ إرسال الآن", callback_data="broadcast_confirm"))
    markup.add(telebot.types.InlineKeyboardButton("❌ إلغاء", callback_data="broadcast_cancel"))
    return markup

def get_welcome_text(first_name: str) -> str:
    custom_message = db.get_setting("welcome_message")
    if custom_message:
        return custom_message.replace("{name}", first_name)
    return (f"أهلاً بك يا <b>{first_name}</b> في بوت تحميل من السوشيال ميديا! 🌹\n"
            "بـوتـنـا سـهـل الاسـتـخـدام..\n"
            "كـل مـا عـلـيـك فـعـلـه هـو إرسـال الـرابط أو إعـادة توجيهه إلـيـنـا.\n\n"
            "يـمـكـنـك الـتـحـمـيـل مـن:\n"
            "• تـيـك تـوك • إنـسـتـغـرام • فـيـسـبـوك • بـيـنـتـرسـت\n\n"
            "شـكـراً لـكـم! ✨")

@bot.message_handler(commands=["start", "help"])
def handle_start(message: telebot.types.Message) -> None:
    user = message.from_user
    db.add_or_update_user(user.id, user.username or "N/A", user.first_name or "User", user.language_code or "ar")
    
    if user.id not in seen_users:
        seen_users.add(user.id)
        username = f"@{user.username}" if user.username else "N/A"
        language = user.language_code if user.language_code else "غير معروف"
        notification = (f"👾 شخص جديد دخل البوت\n👤 الاسم: {user.first_name}\n"
                       f"المعرف: {username}\n🆔 الآيدي: {user.id}\n"
                       f"اللغة: {language}\n📊 إجمالي: {len(seen_users)}")
        notify_admin(notification)
        logger.info("New user saved: user_id=%s", user.id)
    
    user_states.pop(user.id, None)
    bot.send_message(message.chat.id, get_welcome_text(user.first_name),
                    parse_mode="HTML", reply_markup=build_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "batch_download")
def handle_batch_download(call: telebot.types.CallbackQuery) -> None:
    batch_mode_users.add(call.from_user.id)
    user_states[call.from_user.id] = None
    bot.answer_callback_query(call.id)
    bot.edit_message_text("ارسال الروابط مره وحده وانا سوفا اقوم بتحملها لك 📥",
                         call.message.chat.id, call.message.message_id, reply_markup=build_back_keyboard())

def _build_caption_regular_download(message: telebot.types.Message, url: str, platform: str) -> str:
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    return (f"📥 <b>تحميل عادي</b>\n👤 <b>المستخدم:</b> {username}\n"
           f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
           f"🔗 <b>الرابط:</b> <a href=\"{url}\">اضغط هنا</a>\n"
           f"🌐 <b>المنصة:</b> {PLATFORM_EMOJI.get(platform, '🎬')} {platform.upper()}\n"
           f"📅 <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def _process_single_url(message: telebot.types.Message, url: str) -> None:
    status_msg = bot.reply_to(message, "⏳ جارِ التحميل...")
    resolved_url = resolve_url(url)
    _, platform = extract_video_url(resolved_url)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            info = download_video(resolved_url, os.path.join(tmpdir, "video.%(ext)s"), platform or "unknown")
            video_file = find_downloaded_file(tmpdir)
            
            with open(video_file, "rb") as vf:
                video_bytes = vf.read()
            
            regular_channel = channel_manager.get_regular_channel()
            caption = _build_caption_regular_download(message, resolved_url, platform or "unknown")
            
            bot.send_video(regular_channel, video_bytes, caption=caption, parse_mode="HTML", supports_streaming=True)
            send_to_user(message.chat.id, message.from_user.first_name,
                        _method="send_video", video=video_bytes, caption="✅ تم التحميل بنجاح", supports_streaming=True)
            
            Statistics.record_regular_download(message.from_user.id, platform or "unknown", resolved_url)
            bot.delete_message(message.chat.id, status_msg.message_id)
        
        except Exception as e:
            logger.error(f"Download failed: {e}")
            try:
                bot.edit_message_text("❌ حدث خطأ أثناء التحميل. يرجاء إعادة المحاولة...",
                                     message.chat.id, status_msg.message_id)
            except Exception:
                pass

@bot.message_handler(func=lambda m: m.from_user.id in batch_mode_users and not m.text.startswith("/"), content_types=["text"])
def handle_batch_message(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    urls = [u.strip() for u in re.split(r'(?=https?://)', message.text) if u.strip().startswith('http')]
    if not urls:
        return
    batch_mode_users.discard(user_id)
    for url in urls:
        try:
            _process_single_url(message, url)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

@bot.message_handler(func=lambda m: m.from_user.id not in batch_mode_users and user_states.get(m.from_user.id) is None and not m.text.startswith("/"), content_types=["text"])
def handle_regular_download(message: telebot.types.Message) -> None:
    raw_url, platform = extract_video_url(message.text)
    if not raw_url:
        return
    _process_single_url(message, raw_url)

@bot.callback_query_handler(func=lambda call: call.data == "tiktok_clone_start")
def handle_tiktok_clone_start(call: telebot.types.CallbackQuery) -> None:
    bot.answer_callback_query(call.id)
    user_states[call.from_user.id] = "waiting_tiktok_username"
    bot.send_message(call.message.chat.id, "📱 أرسل اسم مستخدم TikTok فقط (بدون رابط)\n✏️ @username أو username")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_tiktok_username" and not m.text.startswith("/"), content_types=["text"])
def handle_tiktok_username_input(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    username_input = message.text.strip()
    if username_input.startswith("@"):
        username_input = username_input[1:]
    
    if not re.match(r"^[a-zA-Z0-9._-]+$", username_input):
        bot.reply_to(message, "❌ صيغة غير صحيحة.")
        return
    
    account_url = f"https://www.tiktok.com/@{username_input}"
    session = tiktok_cloner.start_clone_session(user_id, account_url)
    user_states[user_id] = None
    clone_cancellation[user_id] = False
    bot.send_message(message.chat.id, f"✅ تم حفظ الحساب: <b>@{session['username']}</b>\n\nاختر العملية:",
                    parse_mode="HTML", reply_markup=build_tiktok_clone_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "tiktok_change_account")
def handle_tiktok_change_account(call: telebot.types.CallbackQuery) -> None:
    tiktok_cloner.change_account(call.from_user.id)
    user_states[call.from_user.id] = "waiting_tiktok_username"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🔄 أرسل اسم مستخدم TikTok جديد:")

@bot.callback_query_handler(func=lambda call: call.data == "tiktok_fetch_20")
def handle_tiktok_fetch_20(call: telebot.types.CallbackQuery) -> None:
    user_id = call.from_user.id
    session = tiktok_cloner.get_user_session(user_id)
    if not session:
        bot.answer_callback_query(call.id, "❌ لا توجد جلسة نشطة", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    status_msg = bot.send_message(call.message.chat.id, "⏳ جاري جلب الفيديوهات...", reply_markup=build_clone_cancel_keyboard())
    progress_messages[user_id] = {"chat_id": call.message.chat.id, "message_id": status_msg.message_id}
    clone_cancellation[user_id] = False
    thread = threading.Thread(target=_fetch_tiktok_videos, args=(user_id, session, TIKTOK_BATCH_SIZE, call.message.chat.id))
    thread.daemon = True
    thread.start()
    tiktok_download_threads[user_id] = thread

def _fetch_tiktok_videos(user_id: int, session: Dict, batch_size: int, chat_id: int) -> None:
    try:
        videos = TikTokDownloader.get_account_videos(session['account_url'], session['last_video_index'], batch_size)
        if not videos:
            bot.send_message(chat_id, "❌ لم يتم العثور على فيديوهات")
            return
        
        downloaded_count = 0
        total_videos = len(videos)
        
        for idx, video in enumerate(videos):
            # Check for cancellation
            if clone_cancellation.get(user_id, False):
                bot.send_message(chat_id, f"⛔ تم إلغاء الاستنساخ!\nتم تحميل {downloaded_count} فيديو")
                return
            
            try:
                video_url = video.get('url') or video.get('webpage_url')
                if not video_url:
                    continue
                
                # Update progress
                progress = int((idx / total_videos) * 100)
                progress_text = (f"⏳ جاري التحميل...\n\n"
                               f"📊 التقدم: {progress}%\n"
                               f"🎬 الفيديو {idx + 1}/{total_videos}\n"
                               f"✅ تم تحميل: {downloaded_count}")
                
                if user_id in progress_messages:
                    try:
                        bot.edit_message_text(progress_text, chat_id, progress_messages[user_id]["message_id"],
                                            reply_markup=build_clone_cancel_keyboard())
                    except:
                        pass
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    video_file = TikTokDownloader.download_tiktok_video(video_url, tmpdir, random.choice(USER_AGENTS))
                    if not video_file:
                        continue
                    
                    with open(video_file, "rb") as vf:
                        video_bytes = vf.read()
                    
                    caption = (f"🚀 <b>استنساخ حساب</b>\n👤 <b>المستخدم:</b> @{session['username']}\n"
                              f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                              f"🎬 <b>رقم الفيديو:</b> {session['last_video_index'] + idx + 1}\n"
                              f"📅 <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    send_to_user(chat_id, "User", _method="send_video", video=video_bytes,
                               caption=caption, parse_mode="HTML", supports_streaming=True)
                    clone_channel = channel_manager.get_clone_channel()
                    bot.send_video(clone_channel, video_bytes, caption=caption, parse_mode="HTML", supports_streaming=True)
                    downloaded_count += 1
            except Exception as e:
                logger.warning(f"Error downloading video {idx}: {e}")
                continue
        
        new_index = session['last_video_index'] + downloaded_count
        db.update_tiktok_session(session['session_id'], last_video_index=new_index)
        session['last_video_index'] = new_index
        
        bot.send_message(chat_id, f"✅ تم تحميل {downloaded_count} فيديو\n\nهل تريد تحميل المزيد؟",
                        reply_markup=build_continue_keyboard())
        Statistics.record_tiktok_clone(user_id, session['account_url'], downloaded_count)
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.send_message(chat_id, f"❌ حدث خطأ: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "tiktok_clone_full")
def handle_tiktok_clone_full(call: telebot.types.CallbackQuery) -> None:
    user_id = call.from_user.id
    session = tiktok_cloner.get_user_session(user_id)
    if not session:
        bot.answer_callback_query(call.id, "❌ لا توجد جلسة نشطة", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    status_msg = bot.send_message(call.message.chat.id, "⏳ جاري استنساخ الحساب بالكامل...\n\nقد يستغرق وقتاً طويلاً.", 
                                 reply_markup=build_clone_cancel_keyboard())
    progress_messages[user_id] = {"chat_id": call.message.chat.id, "message_id": status_msg.message_id}
    clone_cancellation[user_id] = False
    thread = threading.Thread(target=_clone_full_account, args=(user_id, session, call.message.chat.id))
    thread.daemon = True
    thread.start()
    tiktok_download_threads[user_id] = thread

def _clone_full_account(user_id: int, session: Dict, chat_id: int) -> None:
    try:
        downloaded_count = 0
        batch_index = session['last_video_index']
        batch_size = TIKTOK_BATCH_SIZE
        total_processed = 0
        
        while True:
            # Check for cancellation
            if clone_cancellation.get(user_id, False):
                bot.send_message(chat_id, f"⛔ تم إلغاء الاستنساخ!\nتم تحميل {downloaded_count} فيديو")
                return
            
            videos = TikTokDownloader.get_account_videos(session['account_url'], batch_index, batch_size)
            if not videos:
                break
            
            for idx, video in enumerate(videos):
                # Check for cancellation again
                if clone_cancellation.get(user_id, False):
                    bot.send_message(chat_id, f"⛔ تم إلغاء الاستنساخ!\nتم تحميل {downloaded_count} فيديو")
                    return
                
                try:
                    video_url = video.get('url') or video.get('webpage_url')
                    if not video_url:
                        continue
                    
                    # Update progress
                    total_processed += 1
                    progress = min((total_processed / 10) * 10, 100)  # Show progress in 10% increments
                    progress_text = (f"⏳ جاري الاستنساخ...\n\n"
                                   f"📊 التقدم: {progress}%\n"
                                   f"✅ تم تحميل: {downloaded_count}")
                    
                    if user_id in progress_messages and total_processed % 2 == 0:
                        try:
                            bot.edit_message_text(progress_text, chat_id, progress_messages[user_id]["message_id"],
                                                reply_markup=build_clone_cancel_keyboard())
                        except:
                            pass
                    
                    with tempfile.TemporaryDirectory() as tmpdir:
                        video_file = TikTokDownloader.download_tiktok_video(video_url, tmpdir, random.choice(USER_AGENTS))
                        if not video_file:
                            continue
                        
                        with open(video_file, "rb") as vf:
                            video_bytes = vf.read()
                        
                        caption = (f"🚀 <b>استنساخ حساب</b>\n👤 <b>المستخدم:</b> @{session['username']}\n"
                                  f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                                  f"🎬 <b>رقم الفيديو:</b> {batch_index + downloaded_count + 1}\n"
                                  f"📅 <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        send_to_user(chat_id, "User", _method="send_video", video=video_bytes,
                                   caption=caption, parse_mode="HTML", supports_streaming=True)
                        clone_channel = channel_manager.get_clone_channel()
                        bot.send_video(clone_channel, video_bytes, caption=caption, parse_mode="HTML", supports_streaming=True)
                        downloaded_count += 1
                except Exception as e:
                    logger.warning(f"Error: {e}")
                    continue
            
            batch_index += len(videos)
        
        db.update_tiktok_session(session['session_id'], last_video_index=batch_index)
        bot.send_message(chat_id, f"✅ انتهى الاستنساخ!\n\nتم تحميل {downloaded_count} فيديو")
        Statistics.record_tiktok_clone(user_id, session['account_url'], downloaded_count)
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.send_message(chat_id, f"❌ حدث خطأ: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_clone")
def handle_cancel_clone(call: telebot.types.CallbackQuery) -> None:
    user_id = call.from_user.id
    clone_cancellation[user_id] = True
    bot.answer_callback_query(call.id, "✅ تم طلب الإلغاء...")
    bot.edit_message_text("⛔ جاري إلغاء الاستنساخ...", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data in ["tiktok_continue", "tiktok_stop"])
def handle_tiktok_continue_stop(call: telebot.types.CallbackQuery) -> None:
    bot.answer_callback_query(call.id)
    if call.data == "tiktok_continue":
        user_id = call.from_user.id
        session = tiktok_cloner.get_user_session(user_id)
        if session:
            bot.send_message(call.message.chat.id, "اختر العملية:", reply_markup=build_tiktok_clone_keyboard())
    else:
        bot.send_message(call.message.chat.id, "✅ تم الإيقاف")

@bot.callback_query_handler(func=lambda call: call.data == "admin_menu")
def handle_admin_menu(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ أنت لست مسؤولاً", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    user_states[call.from_user.id] = None
    bot.edit_message_text("⚙️ <b>لوحة إدارة البوت</b>\n\nاختر العملية المطلوبة:",
                         call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=admin_panel.build_main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_welcome")
def handle_admin_edit_welcome(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "admin_editing_welcome"
    bot.answer_callback_query(call.id)
    current_msg = admin_panel.get_welcome_message()
    bot.send_message(call.message.chat.id, f"✏️ <b>رسالة الترحيب الحالية:</b>\n\n{current_msg}\n\nأرسل الرسالة الجديدة:",
                    parse_mode="HTML")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_editing_welcome" and not m.text.startswith("/"), content_types=["text"])
def handle_welcome_message_input(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    if admin_panel.set_welcome_message(message.text):
        bot.reply_to(message, "✅ تم حفظ رسالة الترحيب الجديدة")
    else:
        bot.reply_to(message, "❌ حدث خطأ")
    user_states[user_id] = None

@bot.callback_query_handler(func=lambda call: call.data == "admin_regular_channel")
def handle_admin_regular_channel(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "admin_setting_regular_channel"
    bot.answer_callback_query(call.id)
    current_channel = channel_manager.get_regular_channel()
    bot.send_message(call.message.chat.id, f"📢 <b>القناة الحالية:</b> <code>{current_channel}</code>\n\nأرسل رابط القناة الجديدة أو اسمها (@channel_name):",
                    parse_mode="HTML")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_setting_regular_channel" and not m.text.startswith("/"), content_types=["text"])
def handle_regular_channel_input(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    channel_id = channel_manager.extract_channel_id(message.text)
    if not channel_id:
        bot.reply_to(message, "❌ صيغة القناة غير صحيحة. أرسل رابط أو @اسم_القناة")
        return
    
    is_admin, result_msg = channel_manager.verify_channel_access(channel_id)
    bot.send_message(message.chat.id, result_msg)
    
    if is_admin:
        if channel_manager.set_regular_channel(channel_id):
            bot.send_message(message.chat.id, f"✅ تم حفظ قناة التحميل العادي: {channel_id}")
        else:
            bot.send_message(message.chat.id, f"❌ فشل حفظ القناة")
    
    user_states[user_id] = None

@bot.callback_query_handler(func=lambda call: call.data == "admin_clone_channel")
def handle_admin_clone_channel(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "admin_setting_clone_channel"
    bot.answer_callback_query(call.id)
    current_channel = channel_manager.get_clone_channel()
    bot.send_message(call.message.chat.id, f"🎬 <b>القناة الحالية:</b> <code>{current_channel}</code>\n\nأرسل رابط القناة الجديدة أو اسمها (@channel_name):",
                    parse_mode="HTML")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_setting_clone_channel" and not m.text.startswith("/"), content_types=["text"])
def handle_clone_channel_input(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    channel_id = channel_manager.extract_channel_id(message.text)
    if not channel_id:
        bot.reply_to(message, "❌ صيغة القناة غير صحيحة. أرسل رابط أو @اسم_القناة")
        return
    
    is_admin, result_msg = channel_manager.verify_channel_access(channel_id)
    bot.send_message(message.chat.id, result_msg)
    
    if is_admin:
        if channel_manager.set_clone_channel(channel_id):
            bot.send_message(message.chat.id, f"✅ تم حفظ قناة الاستنساخ: {channel_id}")
        else:
            bot.send_message(message.chat.id, f"❌ فشل حفظ القناة")
    
    user_states[user_id] = None

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def handle_admin_broadcast(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = None
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📡 <b>اختر نوع المحتوى للإذاعة:</b>",
                    parse_mode="HTML", reply_markup=build_broadcast_type_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_") and call.data not in ["broadcast_confirm", "broadcast_cancel"])
def handle_broadcast_type(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    content_type = call.data.replace("broadcast_", "")
    broadcast_manager.start_broadcast(call.from_user.id, content_type)
    user_states[call.from_user.id] = f"broadcast_waiting_{content_type}"
    bot.answer_callback_query(call.id)
    messages = {
        "text": "📝 أرسل النص:",
        "photo": "🖼️ أرسل الصورة:",
        "video": "🎬 أرسل الفيديو:",
        "audio": "🎵 أرسل الصوت:",
        "document": "📄 أرسل الملف:",
        "sticker": "😊 أرسل الملصق:",
    }
    bot.send_message(call.message.chat.id, messages.get(content_type, "أرسل المحتوى:"))

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, "").startswith("broadcast_waiting_") and not m.text.startswith("/"))
def handle_broadcast_content(message: telebot.types.Message) -> None:
    if not admin_panel.is_admin(message.from_user.id):
        return
    admin_id = message.from_user.id
    if broadcast_manager.set_broadcast_content(admin_id, message):
        bot.send_message(message.chat.id, "✅ تم استقبال المحتوى\n\nهل تريد إرسال هذا المحتوى للجميع؟",
                        reply_markup=build_broadcast_confirm_keyboard())
        user_states[admin_id] = "broadcast_confirm"
    else:
        bot.reply_to(message, "❌ حدث خطأ")

@bot.callback_query_handler(func=lambda call: call.data == "broadcast_confirm")
def handle_broadcast_confirm(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    admin_id = call.from_user.id
    bot.answer_callback_query(call.id)
    status_msg = bot.send_message(call.message.chat.id, "⏳ جاري إرسال الرسائل للجميع...")
    results = broadcast_manager.execute_broadcast(admin_id)
    bot.edit_message_text(
        f"✅ <b>انتهت الإذاعة</b>\n📊 <b>النتائج:</b>\n"
        f"✅ تم الإرسال: {results.get('successful', 0)}\n"
        f"❌ فشل: {results.get('failed', 0)}\n"
        f"🚫 محظورون: {results.get('blocked', 0)}\n"
        f"📈 إجمالي: {results.get('total', 0)}",
        call.message.chat.id, status_msg.message_id, parse_mode="HTML")
    user_states[admin_id] = None

@bot.callback_query_handler(func=lambda call: call.data == "broadcast_cancel")
def handle_broadcast_cancel(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    admin_id = call.from_user.id
    broadcast_manager.cancel_broadcast(admin_id)
    user_states[admin_id] = None
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "✅ تم إلغاء الإذاعة")

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def handle_admin_stats(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    report = Statistics.get_report()
    bot.send_message(call.message.chat.id, report, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "go_back")
def handle_go_back(call: telebot.types.CallbackQuery) -> None:
    batch_mode_users.discard(call.from_user.id)
    user_states[call.from_user.id] = None
    bot.answer_callback_query(call.id)
    bot.edit_message_text(get_welcome_text(call.from_user.first_name),
                         call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=build_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
def handle_admin_back(call: telebot.types.CallbackQuery) -> None:
    if not admin_panel.is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = None
    bot.answer_callback_query(call.id)
    bot.edit_message_text("⚙️ <b>لوحة إدارة البوت</b>\n\nاختر العملية المطلوبة:",
                         call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=admin_panel.build_main_menu_keyboard())

if __name__ == "__main__":
    keep_alive()
    bot.set_my_commands([
        telebot.types.BotCommand("start", "بدء البوت"),
        telebot.types.BotCommand("help", "المساعدة"),
    ])
    logger.info("Bot is running...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, logger_level=logging.WARNING)
        except Exception as e:
            logger.error("Polling crashed: %s — restarting in 5 seconds...", e)
            time.sleep(5)
