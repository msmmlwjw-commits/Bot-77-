import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1520960859"))

# Default channels (can be changed via admin panel)
DEFAULT_REGULAR_CHANNEL_ID = -1003872259900
DEFAULT_CLONE_CHANNEL_ID = -1003872259900

# Logging
LOG_LEVEL = "INFO"

# TikTok cloning
TIKTOK_BATCH_SIZE = 20
TIKTOK_MAX_RETRIES = 3

# File paths
TEMP_DIR = "./temp"
LOGS_DIR = "./logs"
