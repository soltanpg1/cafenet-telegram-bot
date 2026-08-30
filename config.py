import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
CARD_NUMBER = os.getenv("CARD_NUMBER", "0000-0000-0000-0000")
SUPPORT_INFO = os.getenv("SUPPORT_INFO", "برای ارتباط با پشتیبانی پیام ارسال کنید.")
DB_PATH = os.getenv("DB_PATH", "data/bot.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured.")
