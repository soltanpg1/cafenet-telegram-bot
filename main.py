import logging
import re
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from zoneinfo import ZoneInfo

import database as db
import keyboard as kb

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CARD_NUMBER,
    SUPPORT_INFO
)

TEHRAN = ZoneInfo("Asia/Tehran")

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

db.init_db()


# =========================================================
# کمکی
# =========================================================

def normalize_digits(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )
    return text.translate(table)


def is_valid_phone(text):
    text = normalize_digits(text.strip())

    return bool(
        re.fullmatch(
            r"09\d{9}",
            text
        )
    )


def is_valid_amount(text):
    text = normalize_digits(text)
    text = text.replace(",", "").replace("٬", "").replace(" ", "")

    return text.isdigit() and int(text) > 0


def admin_ids_from_config():
    result = []

    if isinstance(ADMIN_IDS, (list, tuple, set)):
        for x in ADMIN_IDS:
            try:
                result.append(int(x))
            except Exception:
                pass

    else:
        try:
            result.append(int(ADMIN_IDS))
        except Exception:
            pass

    return result


def is_admin(user_id):
    if user_id in admin_ids_from_config():
        return True

    return db.get_admin(user_id) is not None


def is_super_admin(user_id):
    return user_id in admin_ids_from_config()


def admin_name(user):
    if user.username:
        return f"@{user.username}"

    if user.full_name:
        return user.full_name

    return str(user.id)


def status_name(status):
    names = {
        "new": "🆕 سفارش جدید",
        "reviewing": "🔍 در حال بررسی",
        "waiting_payment": "💳 در انتظار پرداخت",
        "in_progress": "🔄 در حال انجام",
        "waiting_documents": "📎 منتظر مدارک",
        "completed": "✅ تکمیل‌شده",
        "rejected": "❌ رد شده",
        "cancelled": "❌ لغوشده"
    }

    return names.get(status, status)


def clear_order_state(context):
    keys = [
        "stage",
        "service_id",
        "full_name",
        "phone",
        "description",
        "last_code",
        "support_order_code",
        "admin_order_code",
        "admin_action",
        "upload_more"
    ]

    for key in keys:
        context.user_data.pop(key, None)


async def send_admin_message(
    context,
    text,
    reply_markup=None
):
    admins = db.get_active_admins()

    sent = set()

    # ادمین‌های اصلی از config
    for admin_id in admin_ids_from_config():
        if admin_id not in sent:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=reply_markup
                )
                sent.add(admin_id)
            except Exception as e:
                logger.error(
                    "Could not send admin message to %s: %s",
                    admin_id,
                    e
                )

    # ادمین‌های اضافه‌شده از پنل
    for admin in admins:
        admin_id = admin["user_id"]

        if admin_id in sent:
            continue

        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(
                "Could not send admin message to %s: %s",
                admin_id,
                e
            )


async def send_order_files_to_admins(
    context,
    code
):
    order = db.get_order(code)

    if not order:
        return

    files = db.get_order_files(code)

    if not files:
        return

    admins = []

    for admin_id in admin_ids_from_config():
        admins.append(admin_id)

    for admin in db.get_active_admins():
        if admin["user_id"] not in admins:
            admins.append(admin["user_id"])

    for file_item in files:

        caption = (
            f"📎 مدرک سفارش #{code}\n"
            f"👤 مشتری: {order['full_name']}\n"
            f"🛠 خدمت: {order['service_name']}"
        )

        for admin_id in admins:
            try:

                if file_item["file_type"] == "photo":
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=file_item["telegram_file_id"],
                        caption=caption
                    )

                elif file_item["file_type"] == "document":
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=file_item["telegram_file_id"],
                        caption=caption
                    )

            except Exception as e:
                logger.error(
                    "Could not send file to admin %s: %s",
                    admin_id,
                    e
                )


def jalali_date(gy, gm, gd):
    gdm = [0,31,28,31,30,31,30,31,31,30,31,30,31]
    gy2 = gy - 1600; gm2 = gm - 1; gd2 = gd - 1
    g_day_no = 365*gy2 + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400
    for i in range(gm2): g_day_no += gdm[i+1]
    if gm2 > 1 and ((gy%4==0 and gy%100!=0) or gy%400==0): g_day_no += 1
    g_day_no += gd2
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053; j_day_no %= 12053
    jy = 979 + 33*j_np + 4*(j_day_no//1461); j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no-1)//365; j_day_no = (j_day_no-1)%365
    if j_day_no < 186: jm = 1 + j_day_no//31; jd = 1 + j_day_no%31
    else: jm = 7 + (j_day_no-186)//30; jd = 1 + (j_day_no-186)%30
    return jy, jm, jd

def current_season_prefix():
    now = datetime.now(TEHRAN)
    _, jm, _ = jalali_date(now.year, now.month, now.day)
    return {1:"BH",2:"BH",3:"BH",4:"TA",5:"TA",6:"TA",7:"PZ",8:"PZ",9:"PZ",10:"ZM",11:"ZM",12:"ZM"}[jm]

def report_chat_id():
    raw = os.getenv("REPORT_CHAT_ID", "").strip()
    try: return int(raw) if raw else None
    except ValueError: return None

async def send_completed_report(context, order):
    chat_id = report_chat_id()
    if not chat_id: return
    files = db.get_order_files(order["code"])
    text = (f"📋 گزارش تکمیل سفارش #{order['code']}\n\n"
            f"👤 نام: {order['full_name']}\n📱 موبایل: {order['phone']}\n"
            f"🆔 Telegram ID: {order['user_id']}\n🛠 خدمت: {order['service_name']}\n"
            f"📝 توضیحات: {order['description'] or 'ندارد'}\n"
            f"📎 مدارک: {len(files)} فایل\n💰 مبلغ: {(order['amount'] or 0):,} تومان\n"
            f"👨‍💼 مسئول: {order['admin_name'] or 'نامشخص'}\n"
            f"🕐 تکمیل: {order['completed_at'] or order['updated_at']}")
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
        for f in files:
            if f["file_type"] == "photo": await context.bot.send_photo(chat_id=chat_id, photo=f["telegram_file_id"], caption=f"📎 مدرک سفارش #{order['code']}")
            elif f["file_type"] == "document": await context.bot.send_document(chat_id=chat_id, document=f["telegram_file_id"], caption=f"📎 مدرک سفارش #{order['code']}")
    except Exception as e:
        logger.error("Completed report error: %s", e)

def order_text(order):
    amount = (
        f"{order['amount']:,} تومان"
        if order["amount"]
        else "پس از بررسی"
    )

    file_count = db.get_file_count(order["code"])

    admin_text = (
        order["admin_name"]
        if order["admin_name"]
        else "هنوز اختصاص داده نشده"
    )

    username = (
        f"@{order['username']}"
        if "username" in order.keys() and order["username"]
        else "ندارد"
    )

    return (
        f"📦 سفارش #{order['code']}\n\n"
        f"👤 نام: {order['full_name']}\n"
        f"📱 موبایل: {order['phone']}\n"
        f"🆔 Telegram ID: {order['user_id']}\n"
        f"🔹 Username: {username}\n\n"
        f"🛠 خدمت: {order['service_name']}\n"
        f"📝 توضیحات:\n{order['description'] or 'ندارد'}\n\n"
        f"📎 مدارک: {file_count} فایل\n"
        f"💰 مبلغ: {amount}\n"
        f"📌 وضعیت: {status_name(order['status'])}\n"
        f"👨‍💼 مسئول: {admin_text}\n"
        + (f"❌ دلیل رد: {order['rejection_reason']}\n" if "rejection_reason" in order.keys() and order["rejection_reason"] else "")
        + f"🕐 ثبت: {order['created_at']}"
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args):
        pass

def start_health_server():
    try:
        port = int(os.environ.get("PORT", 10000))
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("HEALTH SERVER STARTED ON PORT %s", port)
    except Exception as e:
        logger.error("Health server error: %s", e)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    db.save_user(user)

    clear_order_state(context)

    logger.info(
        "START COMMAND FROM USER: %s",
        user.id
    )

    await update.message.reply_text(
        "🖥️ منوی اصلی\n\n"
        "به کافینت آنلاین خوش آمدید.\n\n"
        "لطفاً گزینه موردنظر خود را انتخاب کنید:",
        reply_markup=kb.main_menu()
    )


# =========================================================
# ADMIN COMMAND
# =========================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text(
            "⛔ شما دسترسی مدیریت ندارید."
        )
        return

    context.user_data["admin_mode"] = True

    await update.message.reply_text(
        "👨‍💻 پنل مدیریت\n\n"
        "از منوی پایین می‌توانید سفارش‌ها، پرداخت‌ها، "
        "ادمین‌ها و پیام‌های پشتیبانی را مدیریت کنید.",
        reply_markup=kb.admin_reply_keyboard()
    )

    await update.message.reply_text(
        "📊 مدیریت سفارش‌ها و سیستم",
        reply_markup=kb.admin_panel()
    )


# =========================================================
# CALLBACK
# =========================================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    user = query.from_user

    try:

        # =================================================
        # CUSTOMER
        # =================================================

        if data == "main":

            clear_order_state(context)

            await query.edit_message_text(
                "🖥️ منوی اصلی\n\n"
                "لطفاً گزینه موردنظر را انتخاب کنید:",
                reply_markup=kb.main_menu()
            )

            return

        # -----------------------------
        # ثبت سفارش
        # -----------------------------

        if data == "order":

            stage = context.user_data.get("stage")

            if stage:
                await query.edit_message_text(
                    "⚠️ شما در حال تکمیل یک سفارش هستید.\n\n"
                    "اگر سفارش جدیدی را شروع کنید، ممکن است "
                    "روند سفارش فعلی شما به‌هم بخورد.\n\n"
                    "لطفاً انتخاب کنید:",
                    reply_markup=kb.continue_order()
                )
                return

            await query.edit_message_text(
                "🛒 ثبت سفارش\n\n"
                "لطفاً دسته‌بندی خدمت موردنظر خود را انتخاب کنید:",
                reply_markup=kb.category_menu()
            )

            return

        if data == "continue_order":

            stage = context.user_data.get("stage")

            if stage == "name":
                text = "👤 نام و نام خانوادگی خود را ارسال کنید."

            elif stage == "phone":
                text = (
                    "📱 شماره موبایل خود را ارسال کنید.\n\n"
                    "مثال:\n"
                    "09123456789\n"
                    "یا\n"
                    "۰۹۱۲۳۴۵۶۷۸۹"
                )

            elif stage == "description":
                text = "📝 توضیحات سفارش را ارسال کنید."

            elif stage == "file":
                text = (
                    "📎 مدارک خود را ارسال کنید.\n\n"
                    "بعد از ارسال همه مدارک، روی «✅ تمام شد» بزنید."
                )

            else:
                text = "▶️ سفارش قبلی را ادامه دهید."

            await query.edit_message_text(
                text,
                reply_markup=(
                    kb.file_finished()
                    if stage == "file"
                    else None
                )
            )

            return

        if data == "new_order":

            clear_order_state(context)

            await query.edit_message_text(
                "🛒 ثبت سفارش جدید\n\n"
                "لطفاً دسته‌بندی خدمت را انتخاب کنید:",
                reply_markup=kb.category_menu()
            )

            return

        # -----------------------------
        # Category
        # -----------------------------

        if data.startswith("cat:"):

            category_id = int(
                data.split(":")[1]
            )

            category = None

            for c in db.categories():
                if c["id"] == category_id:
                    category = c
                    break

            if not category:
                await query.edit_message_text(
                    "❌ دسته‌بندی پیدا نشد.",
                    reply_markup=kb.back("order")
                )
                return

            await query.edit_message_text(
                f"{category['emoji']} {category['name']}\n\n"
                "لطفاً خدمت موردنظر را انتخاب کنید:",
                reply_markup=kb.service_menu(category_id)
            )

            return

        # -----------------------------
        # Service
        # -----------------------------

        if data.startswith("svc:"):

            service = db.get_service(
                int(data.split(":")[1])
            )

            if not service:
                await query.edit_message_text(
                    "❌ خدمت پیدا نشد.",
                    reply_markup=kb.back("order")
                )
                return

            context.user_data.clear()

            context.user_data["service_id"] = service["id"]
            context.user_data["stage"] = "name"

            await query.edit_message_text(
                f"{service['emoji']} {service['name']}\n\n"
                "برای ادامه ثبت سفارش، اطلاعات زیر دریافت می‌شود.\n\n"
                "👤 لطفاً نام و نام خانوادگی خود را ارسال کنید:"
            )

            return

        # -----------------------------
        # سفارش‌های من
        # -----------------------------

        if data == "myorders":

            orders = db.get_user_orders(
                user.id
            )

            if not orders:
                await query.edit_message_text(
                    "📋 هنوز سفارشی ثبت نکرده‌اید.",
                    reply_markup=kb.back()
                )
                return

            rows = []

            for o in orders[:20]:

                rows.append([
                    InlineKeyboardButton(
                        f"📦 {o['code']} — {o['service_name']}",
                        callback_data=f"detail:{o['code']}"
                    )
                ])

            rows.append([
                InlineKeyboardButton(
                    "🏠 منوی اصلی",
                    callback_data="main"
                )
            ])

            await query.edit_message_text(
                "📋 سفارش‌های من",
                reply_markup=InlineKeyboardMarkup(rows)
            )

            return

        if data.startswith("detail:"):

            code = data.split(":", 1)[1]

            order = db.get_order(
                code,
                user.id
            )

            if not order:
                await query.edit_message_text(
                    "❌ سفارش پیدا نشد.",
                    reply_markup=kb.back("myorders")
                )
                return

            amount = (
                f"{order['amount']:,} تومان"
                if order["amount"]
                else "پس از بررسی"
            )

            file_count = db.get_file_count(code)

            await query.edit_message_text(
                f"📦 سفارش #{order['code']}\n\n"
                f"🛠 خدمت: {order['service_name']}\n"
                f"💰 مبلغ: {amount}\n"
                f"📎 مدارک: {file_count} فایل\n"
                f"📌 وضعیت: {status_name(order['status'])}\n\n"
                f"📝 توضیحات:\n"
                f"{order['description'] or 'ندارد'}",
                reply_markup=kb.back("myorders")
            )

            return

        # -----------------------------
        # تعرفه
        # -----------------------------

        if data == "prices":

            await query.edit_message_text(
                "💰 تعرفه خدمات\n\n"
                "هزینه خدمات بر اساس نوع درخواست، "
                "مدارک موردنیاز و زمان انجام تعیین می‌شود.\n\n"
                "📌 برای خدماتی که قیمت ثابت ندارند، "
                "پس از بررسی سفارش مبلغ دقیق اعلام خواهد شد.",
                reply_markup=kb.back()
            )

            return

        # -----------------------------
        # راهنما
        # -----------------------------

        if data == "help":

            await query.edit_message_text(
                "ℹ️ راهنمای کافینت آنلاین\n\n"
                "🛒 ثبت سفارش\n"
                "خدمت موردنظر خود را انتخاب کنید و اطلاعات "
                "درخواستی را مرحله‌به‌مرحله ارسال کنید.\n\n"
                "📎 ارسال مدارک\n"
                "می‌توانید چند عکس یا فایل ارسال کنید. "
                "پس از پایان ارسال مدارک، گزینه «تمام شد» را بزنید.\n\n"
                "💰 پرداخت\n"
                "پس از بررسی سفارش، مبلغ از طریق همین ربات "
                "به شما اعلام می‌شود.\n\n"
                "💳 رسید پرداخت\n"
                "پس از پرداخت، تصویر یا فایل رسید را ارسال کنید "
                "تا توسط پشتیبانی بررسی شود.\n\n"
                "📋 سفارش‌های من\n"
                "برای مشاهده سفارش‌ها و وضعیت آنها استفاده می‌شود.\n\n"
                "📞 پشتیبانی\n"
                "در صورت وجود سؤال یا مشکل می‌توانید از طریق "
                "بخش پشتیبانی با کارشناسان ارتباط داشته باشید.",
                reply_markup=kb.back()
            )

            return

        # -----------------------------
        # پشتیبانی
        # -----------------------------

        if data == "support":

            context.user_data["stage"] = "support"

            await query.edit_message_text(
                "📞 پشتیبانی\n\n"
                "پیام خود را ارسال کنید تا برای پشتیبانی فرستاده شود.\n\n"
                "اگر پیام شما مربوط به یک سفارش است، "
                "شماره سفارش را نیز بنویسید.\n\n"
                "مثال:\n"
                "«برای سفارش CN-1001 سؤال دارم...»",
                reply_markup=kb.back()
            )

            return

        # =================================================
        # FILES
        # =================================================

        if data == "finish_files":

            if context.user_data.get("stage") != "file":
                await query.edit_message_text(
                    "⚠️ در حال حاضر مرحله ارسال مدارک فعال نیست.",
                    reply_markup=kb.main_menu()
                )
                return

            await finish_order(
                query,
                context,
                no_files=False
            )

            return

        if data == "no_files":

            if context.user_data.get("stage") != "file":
                await query.edit_message_text(
                    "⚠️ در حال حاضر مرحله ارسال مدارک فعال نیست.",
                    reply_markup=kb.main_menu()
                )
                return

            await finish_order(
                query,
                context,
                no_files=True
            )

            return

        # =================================================
        # ADMIN
        # =================================================

        if data.startswith("admin_") or \
           data.startswith("take:") or \
           data.startswith("amount:") or \
           data.startswith("payment:") or \
           data.startswith("reply:") or \
           data.startswith("complete:") or \
           data.startswith("approve_payment:") or \
           data.startswith("reject_payment:") or \
           data.startswith("review:") or \
           data.startswith("change_status:") or \
           data.startswith("request_docs:") or \
           data.startswith("reject:") or \
           data.startswith("setstatus:"):

            if not is_admin(user.id):
                await query.answer(
                    "⛔ دسترسی ندارید.",
                    show_alert=True
                )
                return

        # -----------------------------
        # Admin panel
        # -----------------------------

        if data == "admin_panel":

            context.user_data["admin_mode"] = True

            await query.edit_message_text(
                "👨‍💻 پنل مدیریت\n\n"
                "یکی از بخش‌های زیر را انتخاب کنید:",
                reply_markup=kb.admin_panel()
            )

            return

        # -----------------------------
        # Status
        # -----------------------------

        if data.startswith("admin_status:"):

            status = data.split(":", 1)[1]

            if status == "all":
                orders = db.get_all_orders()
                title = "📦 همه سفارش‌ها"
            else:
                orders = db.get_orders_by_status(status)
                title = status_name(status)

            if not orders:

                await query.edit_message_text(
                    f"{title}\n\n"
                    "📭 سفارشی در این بخش وجود ندارد.",
                    reply_markup=kb.admin_panel()
                )

                return

            rows = []

            for order in orders[:30]:

                rows.append([
                    InlineKeyboardButton(
                        f"#{order['code']} | "
                        f"{order['service_name'][:25]}",
                        callback_data=f"admin_order:{order['code']}"
                    )
                ])

            rows.append([
                InlineKeyboardButton(
                    "🔙 پنل مدیریت",
                    callback_data="admin_panel"
                )
            ])

            await query.edit_message_text(
                f"{title}\n\n"
                f"تعداد سفارش‌ها: {len(orders)}",
                reply_markup=InlineKeyboardMarkup(rows)
            )

            return

        # -----------------------------
        # Admin order detail
        # -----------------------------

        if data.startswith("admin_order:"):

            code = data.split(":", 1)[1]

            order = db.get_order(code)

            if not order:
                await query.edit_message_text(
                    "❌ سفارش پیدا نشد.",
                    reply_markup=kb.admin_panel()
                )
                return

            await query.edit_message_text(
                order_text(order),
                reply_markup=kb.admin_order_buttons(
                    code,
                    order["status"]
                )
            )

            return

        # -----------------------------
        # Take order
        # -----------------------------

        if data.startswith("take:"):

            code = data.split(":", 1)[1]

            success, reason = db.assign_order(
                code,
                user.id,
                admin_name(user)
            )

            if not success:

                if reason == "already_assigned":
                    message = "⚠️ این سفارش قبلاً توسط یک ادمین دریافت شده است."
                elif reason == "quota_full":
                    message = "⛔ سهمیه روزانه شما برای پذیرش سفارش تکمیل شده است."
                else:
                    message = "❌ سفارش پیدا نشد."

                await query.edit_message_text(
                    message,
                    reply_markup=kb.admin_panel()
                )
                return

            order = db.get_order(code)

            # اطلاع به مشتری
            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"🔄 سفارش #{code} وارد مرحله انجام شد.\n\n"
                        "کارشناس کافینت در حال بررسی و انجام "
                        "درخواست شماست.\n\n"
                        "در صورت نیاز به اطلاعات یا مدارک بیشتر، "
                        "از طریق همین ربات با شما ارتباط گرفته خواهد شد."
                    )
                )
            except Exception as e:
                logger.error(
                    "Customer notification error: %s",
                    e
                )

            await query.edit_message_text(
                order_text(order),
                reply_markup=kb.admin_order_buttons(
                    code,
                    "in_progress"
                )
            )

            return

        # -----------------------------
        # تعیین مبلغ
        # -----------------------------

        if data.startswith("amount:"):

            code = data.split(":", 1)[1]

            order = db.get_order(code)

            if not order:
                await query.edit_message_text(
                    "❌ سفارش پیدا نشد.",
                    reply_markup=kb.admin_panel()
                )
                return

            context.user_data["admin_action"] = "amount"
            context.user_data["admin_order_code"] = code

            await query.edit_message_text(
                f"💰 تعیین مبلغ سفارش #{code}\n\n"
                "مبلغ را فقط به صورت عدد ارسال کنید.\n\n"
                "مثال:\n"
                "250000\n\n"
                "یا:\n"
                "۲۵۰۰۰۰"
            )

            return

        # -----------------------------
        # پیام به مشتری
        # -----------------------------

        if data.startswith("reply:"):

            code = data.split(":", 1)[1]

            order = db.get_order(code)

            if not order:
                await query.edit_message_text(
                    "❌ سفارش پیدا نشد.",
                    reply_markup=kb.admin_panel()
                )
                return

            context.user_data["admin_action"] = "reply_customer"
            context.user_data["admin_order_code"] = code

            await query.edit_message_text(
                f"💬 پاسخ به مشتری\n\n"
                f"سفارش: #{code}\n\n"
                "پیام خود را ارسال کنید:"
            )

            return

        # -----------------------------
        # تکمیل سفارش
        # -----------------------------

        if data.startswith("complete:"):

            code = data.split(":", 1)[1]

            order = db.get_order(code)

            if not order:
                await query.edit_message_text(
                    "❌ سفارش پیدا نشد.",
                    reply_markup=kb.admin_panel()
                )
                return

            db.set_status(
                code,
                "completed",
                user.id,
                admin_name(user),
                "سفارش توسط ادمین تکمیل شد"
            )

            completed_order = db.get_order(code)
            await send_completed_report(context, completed_order)

            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"✅ سفارش #{code} با موفقیت تکمیل شد.\n\n"
                        "از اعتماد شما به کافینت آنلاین سپاسگزاریم. 🌹"
                    ),
                    reply_markup=kb.main_menu()
                )
            except Exception as e:
                logger.error(
                    "Completion notification error: %s",
                    e
                )

            await query.edit_message_text(
                f"✅ سفارش #{code} تکمیل شد.\n\n"
                f"👨‍💼 انجام‌دهنده: {admin_name(user)}",
                reply_markup=kb.admin_panel()
            )

            return

        # -----------------------------
        # Payment detail
        # -----------------------------

        if data.startswith("payment:"):

            code = data.split(":", 1)[1]

            payment = db.get_pending_payment(code)

            if not payment:

                await query.edit_message_text(
                    "📭 رسید پرداخت در انتظار بررسی برای این سفارش وجود ندارد.",
                    reply_markup=kb.admin_panel()
                )

                return

            await query.edit_message_text(
                f"💳 رسید پرداخت\n\n"
                f"📦 سفارش: #{code}\n"
                f"💰 مبلغ: {payment['amount']:,} تومان\n"
                f"📌 وضعیت: در انتظار بررسی",
                reply_markup=kb.payment_buttons(
                    code,
                    payment["id"]
                )
            )

            # خود رسید را برای ادمین ارسال می‌کنیم
            try:

                if payment["receipt_type"] == "photo":
                    await context.bot.send_photo(
                        chat_id=user.id,
                        photo=payment["receipt_file_id"],
                        caption=f"🧾 رسید پرداخت سفارش #{code}"
                    )
                else:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=payment["receipt_file_id"],
                        caption=f"🧾 رسید پرداخت سفارش #{code}"
                    )

            except Exception as e:
                logger.error(
                    "Could not resend payment receipt: %s",
                    e
                )

            return

        # -----------------------------
        # تأیید پرداخت
        # -----------------------------

        if data.startswith("approve_payment:"):

            parts = data.split(":")

            payment_id = int(parts[1])
            code = parts[2]

            order_id = db.set_payment_status_and_order(
                payment_id,
                "approved"
            )

            if not order_id:
                await query.edit_message_text(
                    "❌ رسید پرداخت پیدا نشد.",
                    reply_markup=kb.admin_panel()
                )
                return

            db.set_status(
                code,
                "in_progress",
                user.id,
                admin_name(user),
                "پرداخت توسط ادمین تأیید شد"
            )

            order = db.get_order(code)

            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"✅ پرداخت سفارش #{code} تأیید شد.\n\n"
                        "پرداخت شما با موفقیت بررسی شد.\n"
                        "سفارش وارد مرحله انجام شده است. 🔄"
                    ),
                    reply_markup=kb.main_menu()
                )
            except Exception as e:
                logger.error(
                    "Payment approval notification: %s",
                    e
                )

            await query.edit_message_text(
                f"✅ پرداخت سفارش #{code} تأیید شد.\n\n"
                f"👨‍💼 بررسی‌کننده: {admin_name(user)}",
                reply_markup=kb.admin_panel()
            )

            return

        # -----------------------------
        # رد پرداخت
        # -----------------------------

        if data.startswith("reject_payment:"):

            parts = data.split(":")

            payment_id = int(parts[1])
            code = parts[2]

            order_id = db.set_payment_status_and_order(
                payment_id,
                "rejected"
            )

            if not order_id:
                await query.edit_message_text(
                    "❌ رسید پرداخت پیدا نشد.",
                    reply_markup=kb.admin_panel()
                )
                return

            order = db.get_order(code)

            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"⚠️ رسید پرداخت سفارش #{code} تأیید نشد.\n\n"
                        "لطفاً اطلاعات پرداخت را بررسی کرده و "
                        "رسید صحیح را دوباره ارسال کنید."
                    )
                )
            except Exception as e:
                logger.error(
                    "Payment rejection notification: %s",
                    e
                )

            await query.edit_message_text(
                f"❌ رسید پرداخت سفارش #{code} رد شد.",
                reply_markup=kb.admin_panel()
            )

            return

        # -----------------------------
        # Admin management
        # -----------------------------

        if data == "admin_manage":

            if not is_super_admin(user.id):
                await query.edit_message_text(
                    "⛔ فقط ادمین اصلی اجازه مدیریت ادمین‌ها را دارد.",
                    reply_markup=kb.admin_panel()
                )
                return

            await query.edit_message_text(
                "👥 مدیریت ادمین‌ها\n\n"
                "از این بخش می‌توانید ادمین‌های سیستم را "
                "اضافه یا حذف کنید.",
                reply_markup=kb.admin_management()
            )

            return

        if data == "admin_list":

            if not is_super_admin(user.id):
                return

            admins = db.get_all_admins()

            text = "👥 لیست ادمین‌ها\n\n"

            if not admins:
                text += "ادمین اضافه‌ای ثبت نشده است."

            else:

                for i, admin_item in enumerate(admins, 1):

                    status = (
                        "🟢 فعال"
                        if admin_item["active"]
                        else "🔴 غیرفعال"
                    )

                    role = (
                        "👑 ادمین اصلی"
                        if admin_item["role"] == "owner"
                        else "👨‍💼 ادمین"
                    )

                    text += (
                        f"{i}. {role}\n"
                        f"نام: {admin_item['full_name']}\n"
                        f"ID: {admin_item['user_id']}\n"
                        f"وضعیت: {status}\n\n"
                    )

            await query.edit_message_text(
                text,
                reply_markup=kb.admin_management()
            )

            return

        if data == "add_admin":

            if not is_super_admin(user.id):
                return

            context.user_data["admin_action"] = "add_admin"

            await query.edit_message_text(
                "➕ افزودن ادمین\n\n"
                "Telegram ID شخص موردنظر را ارسال کنید.\n\n"
                "مثال:\n"
                "123456789"
            )

            return

        if data == "remove_admin":

            if not is_super_admin(user.id):
                return

            context.user_data["admin_action"] = "remove_admin"

            await query.edit_message_text(
                "➖ حذف ادمین\n\n"
                "Telegram ID ادمینی که می‌خواهید حذف شود را ارسال کنید."
            )

            return

        if data == "admin_support":

            await query.edit_message_text(
                "💬 پیام‌های پشتیبانی\n\n"
                "پیام‌های جدید مشتریان از طریق اعلان‌های "
                "ادمین برای شما ارسال می‌شوند.",
                reply_markup=kb.admin_panel()
            )

            return

        if data.startswith("review:"):
            code=data.split(":",1)[1]
            if db.set_status(code,"reviewing",user.id,admin_name(user),"سفارش به در حال بررسی منتقل شد"):
                await query.edit_message_text(order_text(db.get_order(code)), reply_markup=kb.admin_order_buttons(code,"reviewing"))
            return

        if data.startswith("change_status:"):
            code=data.split(":",1)[1]
            if db.get_order(code):
                await query.edit_message_text(f"🔄 تغییر وضعیت سفارش #{code}\n\nوضعیت جدید را انتخاب کنید:", reply_markup=kb.status_change_menu(code))
            return

        if data == "change_status":
            context.user_data["admin_action"]="change_status_code"
            await query.edit_message_text("🔄 تغییر وضعیت سفارش\n\nشماره سفارش را ارسال کنید:")
            return

        if data.startswith("setstatus:"):
            _,status,code=data.split(":",2)
            db.set_status(code,status,user.id,admin_name(user),f"تغییر دستی وضعیت به {status_name(status)}")
            order=db.get_order(code)
            if status == "completed":
                await send_completed_report(context, order)
                try:
                    await context.bot.send_message(chat_id=order["user_id"], text=f"✅ سفارش #{code} تکمیل شد.", reply_markup=kb.main_menu())
                except Exception: pass
            await query.edit_message_text(order_text(order), reply_markup=kb.admin_order_buttons(code,status))
            return

        if data.startswith("request_docs:"):
            code=data.split(":",1)[1]
            order=db.get_order(code)
            if not order: return
            db.set_status(code,"waiting_documents",user.id,admin_name(user),"ادمین درخواست مدارک بیشتر کرد")
            try:
                await context.bot.send_message(chat_id=order["user_id"], text=f"📎 برای سفارش #{code} به مدارک یا اطلاعات بیشتری نیاز است.\n\nلطفاً مدارک موردنیاز را از طریق دکمه زیر ارسال کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📎 ارسال مدارک بیشتر", callback_data=f"upload_more:{code}")]]))
            except Exception as e: logger.error("Request docs notify error: %s",e)
            await query.edit_message_text("✅ درخواست مدارک بیشتر برای مشتری ارسال شد.", reply_markup=kb.admin_panel())
            return

        if data == "request_docs":
            context.user_data["admin_action"]="request_docs_code"
            await query.edit_message_text("📎 درخواست مدارک بیشتر\n\nشماره سفارش را ارسال کنید:")
            return

        if data.startswith("reject:"):
            code=data.split(":",1)[1]
            context.user_data["admin_action"]="reject_reason"
            context.user_data["admin_order_code"]=code
            await query.edit_message_text(f"❌ رد سفارش #{code}\n\nلطفاً دلیل رد سفارش را ارسال کنید:")
            return

        if data.startswith("upload_more:"):
            code=data.split(":",1)[1]
            order=db.get_order(code,user.id)
            if not order: return
            context.user_data["stage"]="file"; context.user_data["last_code"]=code; context.user_data["upload_more"]=True
            await query.edit_message_text("📎 لطفاً مدارک بیشتر را ارسال کنید.\n\nپس از پایان، «✅ تمام شد» را بزنید.", reply_markup=kb.file_finished())
            return

        if data == "settings_status":
            r=db.status_report()
            await query.edit_message_text(f"📊 وضعیت سفارش‌ها\n\n🆕 جدید: {r['new']}\n🔍 در حال بررسی: {r['reviewing']}\n🔄 در حال انجام: {r['in_progress']}\n💳 در انتظار پرداخت: {r['waiting_payment']}\n📎 منتظر مدارک: {r['waiting_documents']}\n❌ رد شده: {r['rejected']}\n✅ تکمیل‌شده: {r['completed']}\n📦 کل: {r['total']}\n\n📅 ۷ روز گذشته: {r['week']}\n📅 ۳۰ روز گذشته: {r['month']}\n📅 ۳۶۵ روز گذشته: {r['year']}", reply_markup=kb.admin_settings())
            return

        if data == "set_capacity":
            if not is_super_admin(user.id): return
            context.user_data["admin_action"]="set_capacity"
            await query.edit_message_text(f"📈 ظرفیت روزانه کل\n\nظرفیت فعلی: {db.get_daily_capacity() or 'نامحدود'}\n\nعدد ظرفیت را ارسال کنید. برای نامحدود 0 بفرستید.")
            return

        if data == "set_card_number":
            if not is_super_admin(user.id): return
            context.user_data["admin_action"]="set_card_number"
            await query.edit_message_text("💳 شماره کارت جدید را ارسال کنید:")
            return

        if data == "set_card_holder":
            if not is_super_admin(user.id): return
            context.user_data["admin_action"]="set_card_holder"
            await query.edit_message_text("👤 نام صاحب کارت جدید را ارسال کنید:")
            return

        if data == "admin_quotas":
            if not is_super_admin(user.id): return
            admins=db.get_active_admins()
            text="🎯 سهمیه روزانه ادمین‌ها\n\n"
            for a in admins:
                lim=db.get_admin_daily_limit(a["user_id"]); used=db.count_admin_orders_today(a["user_id"])
                text += f"👤 {a['full_name'] or a['user_id']} | ID: {a['user_id']} | امروز: {used} | سهمیه: {lim or 'نامحدود'}\n"
            await query.edit_message_text(text+"\nبرای تغییر سهمیه، روی دکمه زیر بزنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎯 تغییر سهمیه", callback_data="set_quota")],[InlineKeyboardButton("🔙 تنظیمات",callback_data="admin_settings")]]))
            return

        if data == "set_quota":
            if not is_super_admin(user.id): return
            context.user_data["admin_action"]="set_quota_id"
            await query.edit_message_text("🎯 ابتدا Telegram ID ادمین را ارسال کنید:")
            return

        if data == "admin_settings":
            if not is_super_admin(user.id):
                await query.answer("⛔ فقط ادمین اصلی به تنظیمات دسترسی دارد.", show_alert=True)
                return
            await query.edit_message_text("⚙️ تنظیمات سیستم\n\nبخش موردنظر را انتخاب کنید:", reply_markup=kb.admin_settings())
            return

        raise ValueError(
            f"Unknown callback: {data}"
        )

    except Exception as e:

        logger.exception(
            "Callback error: %s",
            e
        )

        try:
            await query.edit_message_text(
                "❌ هنگام پردازش درخواست مشکلی پیش آمد.\n\n"
                "خطا در سیستم ثبت شد. لطفاً دوباره تلاش کنید.",
                reply_markup=(
                    kb.admin_panel()
                    if is_admin(user.id)
                    else kb.main_menu()
                )
            )
        except Exception:
            pass


# =========================================================
# TEXT MESSAGE
# =========================================================

async def text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user
    text = update.message.text.strip()

    logger.info(
        "TEXT MESSAGE: user=%s, stage=%s, admin_action=%s",
        user.id,
        context.user_data.get("stage"),
        context.user_data.get("admin_action")
    )

    # =====================================================
    # ADMIN TEXT MENU
    # =====================================================

    if is_admin(user.id):

        if text == "👨‍💻 پنل مدیریت":

            context.user_data["admin_mode"] = True

            await update.message.reply_text(
                "👨‍💻 پنل مدیریت",
                reply_markup=kb.admin_panel()
            )

            return

        if text == "📦 همه سفارش‌ها":
            await show_admin_status(update, context, "all"); return
        if text == "🔍 در حال بررسی":
            await show_admin_status(update, context, "reviewing"); return
        if text == "📎 منتظر مدارک":
            await show_admin_status(update, context, "waiting_documents"); return
        if text == "❌ رد شده":
            await show_admin_status(update, context, "rejected"); return
        if text == "🔄 تغییر وضعیت سفارش":
            context.user_data["admin_action"]="change_status_code"; await update.message.reply_text("🔄 شماره سفارش را ارسال کنید:"); return
        if text == "📎 درخواست مدارک بیشتر":
            context.user_data["admin_action"]="request_docs_code"; await update.message.reply_text("📎 شماره سفارش را ارسال کنید:"); return
        if text == "👤 پنل مشتری":
            context.user_data["admin_mode"]=False; await update.message.reply_text("🏠 پنل مشتری",reply_markup=kb.main_menu()); return
        if text == "⚙️ تنظیمات":
            if not is_super_admin(user.id): await update.message.reply_text("⛔ فقط ادمین اصلی به تنظیمات دسترسی دارد."); return
            await update.message.reply_text("⚙️ تنظیمات",reply_markup=kb.admin_settings()); return

        if text == "🆕 سفارش‌های جدید":

            await show_admin_status(
                update,
                "new"
            )
            return

        if text == "💳 در انتظار پرداخت":

            await show_admin_status(
                update,
                "waiting_payment"
            )
            return

        if text == "🔄 در حال انجام":

            await show_admin_status(
                update,
                "in_progress"
            )
            return

        if text == "✅ تکمیل‌شده":

            await show_admin_status(
                update,
                "completed"
            )
            return

        if text == "📦 همه سفارش‌ها":

            await show_admin_status(
                update,
                "all"
            )
            return

        if text == "👥 مدیریت ادمین‌ها":

            if is_super_admin(user.id):
                await update.message.reply_text(
                    "👥 مدیریت ادمین‌ها",
                    reply_markup=kb.admin_management()
                )
            else:
                await update.message.reply_text(
                    "⛔ فقط ادمین اصلی اجازه این کار را دارد."
                )

            return

        if text == "💬 پیام‌های پشتیبانی":

            await update.message.reply_text(
                "💬 پیام‌های پشتیبانی\n\n"
                "پیام‌های مشتریان در همین پنل برای شما ارسال می‌شوند.",
                reply_markup=kb.admin_panel()
            )

            return

        if text == "⚙️ تنظیمات":

            await update.message.reply_text(
                "⚙️ تنظیمات",
                reply_markup=kb.admin_panel()
            )

            return

        if text == "🏠 خروج از پنل":

            context.user_data["admin_mode"] = False

            await update.message.reply_text(
                "🏠 به منوی مشتری برگشتید.",
                reply_markup=kb.main_menu()
            )

            return

        # =================================================
        # ADMIN ACTIONS
        # =================================================

        action = context.user_data.get("admin_action")

        if action == "amount":

            code = context.user_data.get(
                "admin_order_code"
            )

            if not code:
                context.user_data.pop(
                    "admin_action",
                    None
                )

            elif not is_valid_amount(text):

                await update.message.reply_text(
                    "❌ مبلغ نامعتبر است.\n\n"
                    "لطفاً فقط عدد وارد کنید.\n\n"
                    "مثال:\n"
                    "250000\n"
                    "یا\n"
                    "۲۵۰۰۰۰"
                )
                return

            else:

                amount = int(
                    normalize_digits(text)
                    .replace(",", "")
                    .replace("٬", "")
                    .replace(" ", "")
                )

                db.set_amount(
                    code,
                    amount,
                    user.id,
                    admin_name(user)
                )

                order = db.get_order(code)

                try:

                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            f"💰 مبلغ سفارش #{code} مشخص شد.\n\n"
                            f"💵 مبلغ قابل پرداخت:\n"
                            f"{amount:,} تومان\n\n"
                            "برای پرداخت روی دکمه زیر بزنید."
                        ),
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    "💳 پرداخت",
                                    callback_data=f"pay:{code}"
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    "📋 مشاهده سفارش",
                                    callback_data=f"detail:{code}"
                                )
                            ]
                        ])
                    )

                except Exception as e:
                    logger.error(
                        "Could not notify customer about amount: %s",
                        e
                    )

                context.user_data.pop(
                    "admin_action",
                    None
                )

                context.user_data.pop(
                    "admin_order_code",
                    None
                )

                await update.message.reply_text(
                    f"✅ مبلغ سفارش #{code} ثبت شد.\n\n"
                    f"💰 {amount:,} تومان\n\n"
                    "مبلغ برای مشتری ارسال شد.",
                    reply_markup=kb.admin_reply_keyboard()
                )

                return

        if action == "reply_customer":

            code = context.user_data.get(
                "admin_order_code"
            )

            if not code:
                return

            order = db.get_order(code)

            if not order:
                await update.message.reply_text(
                    "❌ سفارش پیدا نشد."
                )
                return

            db.save_support_message(
                order["user_id"],
                code,
                "admin_to_user",
                text,
                update.message.message_id
            )

            try:

                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"💬 پیام پشتیبانی\n"
                        f"📦 سفارش #{code}\n\n"
                        f"{text}"
                    )
                )

            except Exception as e:

                await update.message.reply_text(
                    "❌ ارسال پیام به مشتری انجام نشد."
                )

                logger.error(
                    "Admin reply error: %s",
                    e
                )

                return

            context.user_data.pop(
                "admin_action",
                None
            )

            context.user_data.pop(
                "admin_order_code",
                None
            )

            await update.message.reply_text(
                "✅ پیام برای مشتری ارسال شد.",
                reply_markup=kb.admin_reply_keyboard()
            )

            return

        if action == "add_admin":

            if not is_super_admin(user.id):
                return

            value = normalize_digits(text)

            if not value.isdigit():

                await update.message.reply_text(
                    "❌ Telegram ID باید فقط عدد باشد."
                )
                return

            target_id = int(value)

            # کاربر را اگر وجود دارد پیدا می‌کنیم
            with db.connect() as database:
                target = database.execute(
                    """
                    SELECT *
                    FROM users
                    WHERE id=?
                    """,
                    (target_id,)
                ).fetchone()

            username = (
                target["username"]
                if target
                else ""
            )

            full_name = (
                target["full_name"]
                if target
                else f"Admin {target_id}"
            )

            db.add_admin(
                target_id,
                username,
                full_name,
                "admin"
            )

            context.user_data.pop(
                "admin_action",
                None
            )

            await update.message.reply_text(
                "✅ ادمین با موفقیت اضافه شد.\n\n"
                f"🆔 ID: {target_id}\n"
                f"👤 نام: {full_name}",
                reply_markup=kb.admin_reply_keyboard()
            )

            return

        if action == "remove_admin":

            if not is_super_admin(user.id):
                return

            value = normalize_digits(text)

            if not value.isdigit():

                await update.message.reply_text(
                    "❌ Telegram ID باید فقط عدد باشد."
                )
                return

            target_id = int(value)

            if target_id in admin_ids_from_config():

                await update.message.reply_text(
                    "⛔ ادمین اصلی از طریق این بخش قابل حذف نیست."
                )
                return

            db.remove_admin(
                target_id
            )

            context.user_data.pop(
                "admin_action",
                None
            )

            await update.message.reply_text(
                "✅ ادمین غیرفعال شد.",
                reply_markup=kb.admin_reply_keyboard()
            )

            return

        if action == "change_status_code":
            code=text.strip()
            if db.get_order(code):
                context.user_data.pop("admin_action",None)
                await update.message.reply_text("وضعیت جدید را انتخاب کنید:", reply_markup=kb.status_change_menu(code))
            else: await update.message.reply_text("❌ سفارش پیدا نشد.")
            return

        if action == "request_docs_code":
            code=text.strip(); order=db.get_order(code)
            context.user_data.pop("admin_action",None)
            if not order: await update.message.reply_text("❌ سفارش پیدا نشد."); return
            db.set_status(code,"waiting_documents",user.id,admin_name(user),"ادمین درخواست مدارک بیشتر کرد")
            await context.bot.send_message(chat_id=order["user_id"],text=f"📎 برای سفارش #{code} مدارک بیشتری لازم است.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📎 ارسال مدارک بیشتر",callback_data=f"upload_more:{code}")]]))
            await update.message.reply_text("✅ درخواست برای مشتری ارسال شد.",reply_markup=kb.admin_reply_keyboard()); return

        if action == "reject_reason":
            code=context.user_data.get("admin_order_code"); order=db.get_order(code) if code else None
            if not order: return
            with db.connect() as d:
                d.execute("UPDATE orders SET rejection_reason=?, updated_at=? WHERE code=?",(text, datetime.now(TEHRAN).strftime("%Y-%m-%d %H:%M:%S"),code))
            db.set_status(code,"rejected",user.id,admin_name(user),f"دلیل رد: {text}")
            try: await context.bot.send_message(chat_id=order["user_id"],text=f"❌ سفارش #{code} رد شد.\n\nدلیل: {text}")
            except Exception: pass
            context.user_data.pop("admin_action",None); context.user_data.pop("admin_order_code",None)
            await update.message.reply_text("✅ سفارش رد شد و دلیل ثبت گردید.",reply_markup=kb.admin_reply_keyboard()); return

        if action == "set_capacity":
            if not is_super_admin(user.id): return
            v=normalize_digits(text).replace(",","").replace("٬","").strip()
            if not v.isdigit(): await update.message.reply_text("❌ فقط عدد وارد کنید."); return
            db.set_daily_capacity(int(v)); context.user_data.pop("admin_action",None)
            await update.message.reply_text(f"✅ ظرفیت روزانه روی {int(v) or 'نامحدود'} تنظیم شد.",reply_markup=kb.admin_reply_keyboard()); return

        if action == "set_card_number":
            if not is_super_admin(user.id): return
            db.set_card_settings(card_number=normalize_digits(text).replace(" ","")); context.user_data.pop("admin_action",None)
            await update.message.reply_text("✅ شماره کارت تغییر کرد.",reply_markup=kb.admin_reply_keyboard()); return

        if action == "set_card_holder":
            if not is_super_admin(user.id): return
            db.set_card_settings(card_holder=text); context.user_data.pop("admin_action",None)
            await update.message.reply_text("✅ نام صاحب کارت تغییر کرد.",reply_markup=kb.admin_reply_keyboard()); return

        if action == "set_quota_id":
            if not is_super_admin(user.id): return
            v=normalize_digits(text).strip()
            if not v.isdigit(): await update.message.reply_text("❌ Telegram ID باید عدد باشد."); return
            context.user_data["quota_admin_id"]=int(v); context.user_data["admin_action"]="set_quota_value"
            await update.message.reply_text("🎯 مقدار سهمیه روزانه را ارسال کنید. برای نامحدود 0 بفرستید:"); return

        if action == "set_quota_value":
            if not is_super_admin(user.id): return
            v=normalize_digits(text).replace(",","").replace("٬","").strip()
            if not v.isdigit(): await update.message.reply_text("❌ فقط عدد وارد کنید."); return
            aid=context.user_data.get("quota_admin_id")
            db.set_admin_daily_limit(aid,int(v)); context.user_data.pop("admin_action",None); context.user_data.pop("quota_admin_id",None)
            await update.message.reply_text("✅ سهمیه ادمین تنظیم شد.",reply_markup=kb.admin_reply_keyboard()); return

    # =====================================================
    # CUSTOMER STAGES
    # =====================================================

    stage = context.user_data.get("stage")

    if stage == "support":

        # ذخیره پیام
        db.save_support_message(
            user.id,
            None,
            "user_to_admin",
            text,
            update.message.message_id
        )

        admin_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "💬 پاسخ به مشتری",
                    callback_data=f"support_reply:{user.id}"
                )
            ]
        ])

        await send_admin_message(
            context,
            (
                "📞 پیام جدید پشتیبانی\n\n"
                f"👤 نام: {user.full_name}\n"
                f"🆔 Telegram ID: {user.id}\n"
                f"🔹 Username: @{user.username if user.username else 'ندارد'}\n\n"
                f"💬 پیام:\n{text}"
            ),
            admin_keyboard
        )

        await update.message.reply_text(
            "✅ پیام شما برای پشتیبانی ارسال شد.\n\n"
            "کارشناس پس از بررسی از طریق همین ربات با شما ارتباط خواهد گرفت.",
            reply_markup=kb.main_menu()
        )

        context.user_data.pop(
            "stage",
            None
        )

        return

    if stage == "name":

        if len(text) < 3:

            await update.message.reply_text(
                "❌ لطفاً نام و نام خانوادگی معتبر وارد کنید."
            )
            return

        context.user_data["full_name"] = text
        context.user_data["stage"] = "phone"

        await update.message.reply_text(
            "📱 شماره موبایل خود را ارسال کنید.\n\n"
            "مثال:\n"
            "09123456789\n"
            "یا\n"
            "۰۹۱۲۳۴۵۶۷۸۹\n\n"
            "⚠️ شماره باید فقط شامل عدد باشد."
        )

        return

    if stage == "phone":

        if not is_valid_phone(text):

            await update.message.reply_text(
                "❌ شماره موبایل صحیح نیست.\n\n"
                "لطفاً فقط شماره موبایل ۱۱ رقمی وارد کنید.\n\n"
                "مثال صحیح:\n"
                "09123456789\n"
                "یا:\n"
                "۰۹۱۲۳۴۵۶۷۸۹"
            )
            return

        context.user_data["phone"] = normalize_digits(
            text
        )

        context.user_data["stage"] = "description"

        await update.message.reply_text(
            "📝 توضیحات سفارش را ارسال کنید.\n\n"
            "اگر توضیح خاصی ندارید، بنویسید:\n"
            "ندارم"
        )

        return

    if stage == "description":

        context.user_data["description"] = text

        context.user_data["stage"] = "file"

        await update.message.reply_text(
            "📎 مدارک و فایل‌های موردنیاز را ارسال کنید.\n\n"
            "می‌توانید چند فایل یا عکس را پشت سر هم بفرستید.\n\n"
            "بعد از ارسال همه مدارک:\n"
            "روی «✅ تمام شد» بزنید.\n\n"
            "اگر هیچ مدرکی ندارید:\n"
            "روی «❌ مدارکی ندارم» بزنید.",
            reply_markup=kb.file_finished()
        )

        return

    if stage == "file":

        await update.message.reply_text(
            "📎 لطفاً فایل یا عکس را ارسال کنید.\n\n"
            "بعد از تمام شدن ارسال مدارک، "
            "روی «✅ تمام شد» بزنید.",
            reply_markup=kb.file_finished()
        )

        return

    # =====================================================
    # PAYMENT RECEIPT
    # =====================================================

    if context.user_data.get("payment_order_code"):

        code = context.user_data.get(
            "payment_order_code"
        )

        order = db.get_order(
            code,
            user.id
        )

        if not order:

            context.user_data.pop(
                "payment_order_code",
                None
            )

            await update.message.reply_text(
                "❌ سفارش پیدا نشد."
            )
            return

        await update.message.reply_text(
            "🧾 لطفاً رسید پرداخت را به صورت عکس یا فایل ارسال کنید."
        )

        return

    await update.message.reply_text(
        "لطفاً از منوی ربات استفاده کنید.",
        reply_markup=kb.main_menu()
    )


# =========================================================
# FILE MESSAGE
# =========================================================

async def file_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    # =====================================================
    # PAYMENT RECEIPT
    # =====================================================

    payment_code = context.user_data.get(
        "payment_order_code"
    )

    if payment_code:

        order = db.get_order(
            payment_code,
            user.id
        )

        if not order:
            context.user_data.pop(
                "payment_order_code",
                None
            )
            return

        file_id = None
        file_type = None

        if update.message.photo:

            file_id = update.message.photo[-1].file_id
            file_type = "photo"

        elif update.message.document:

            file_id = update.message.document.file_id
            file_type = "document"

        if not file_id:
            return

        amount = order["amount"]

        db.add_payment(
            payment_code,
            amount,
            file_id,
            file_type
        )

        payment = db.get_pending_payment(
            payment_code
        )

        await send_admin_message(
            context,
            (
                "🧾 رسید پرداخت جدید\n\n"
                f"📦 سفارش: #{payment_code}\n"
                f"👤 مشتری: {order['full_name']}\n"
                f"📱 موبایل: {order['phone']}\n"
                f"💰 مبلغ: {amount:,} تومان\n\n"
                "⚠️ رسید برای بررسی ارسال شده است."
            ),
            kb.payment_buttons(
                payment_code,
                payment["id"]
            )
        )

        # ارسال خود رسید برای ادمین
        await send_payment_receipt_to_admins(
            context,
            payment
        )

        context.user_data.pop(
            "payment_order_code",
            None
        )

        await update.message.reply_text(
            f"✅ رسید پرداخت سفارش #{payment_code} دریافت شد.\n\n"
            "🧾 رسید برای ادمین ارسال شد.\n"
            "⏳ پس از بررسی نتیجه از طریق همین ربات به شما اطلاع داده می‌شود.",
            reply_markup=kb.main_menu()
        )

        return

    # =====================================================
    # ORDER FILE
    # =====================================================

    if context.user_data.get("stage") != "file":
        return

    code = context.user_data.get(
        "last_code"
    )

    # اگر هنوز سفارش ساخته نشده، اینجا امکان ثبت فایل نیست
    # بنابراین اول سفارش را ثبت می‌کنیم.
    if not code:

        service_id = context.user_data.get(
            "service_id"
        )

        if not service_id:
            await update.message.reply_text(
                "❌ اطلاعات سفارش پیدا نشد. لطفاً دوباره از ثبت سفارش شروع کنید.",
                reply_markup=kb.main_menu()
            )
            return

        service = db.get_service(
            service_id
        )

        if not db.capacity_available():
            limit = db.get_daily_capacity()
            await update.message.reply_text(f"⛔ ظرفیت ثبت سفارش امروز تکمیل شده است.\n\nحداکثر ظرفیت امروز: {limit} سفارش\nلطفاً فردا دوباره تلاش کنید.", reply_markup=kb.main_menu())
            clear_order_state(context)
            return

        if not db.capacity_available():
            limit = db.get_daily_capacity()
            await query.edit_message_text(f"⛔ ظرفیت ثبت سفارش امروز تکمیل شده است.\n\nحداکثر ظرفیت امروز: {limit} سفارش\nلطفاً فردا دوباره تلاش کنید.", reply_markup=kb.main_menu())
            clear_order_state(context)
            return

        code = db.create_order(
            user.id,
            service,
            context.user_data["full_name"],
            context.user_data["phone"],
            context.user_data["description"]
        )

        context.user_data["last_code"] = code

    # ذخیره فایل
    if update.message.document:

        db.add_file(
            code,
            update.message.document.file_id,
            "document",
            update.message.document.file_name or ""
        )

    elif update.message.photo:

        db.add_file(
            code,
            update.message.photo[-1].file_id,
            "photo"
        )

    else:
        return

    # ارسال فایل همین لحظه برای ادمین
    await send_single_file_to_admins(
        context,
        code,
        update
    )

    count = db.get_file_count(
        code
    )

    await update.message.reply_text(
        f"✅ فایل دریافت شد.\n\n"
        f"📦 سفارش: #{code}\n"
        f"📎 تعداد فایل‌های دریافت‌شده: {count}\n\n"
        "اگر فایل دیگری دارید می‌توانید ارسال کنید.\n"
        "پس از پایان، روی «✅ تمام شد» بزنید.",
        reply_markup=kb.file_finished()
    )


# =========================================================
# SEND FILE TO ADMINS
# =========================================================

async def send_single_file_to_admins(
    context,
    code,
    update
):

    order = db.get_order(code)

    if not order:
        return

    file_count = db.get_file_count(code)

    admins = []

    for admin_id in admin_ids_from_config():
        admins.append(admin_id)

    for admin in db.get_active_admins():

        if admin["user_id"] not in admins:
            admins.append(admin["user_id"])

    if update.message.document:

        file_id = update.message.document.file_id
        file_name = (
            update.message.document.file_name
            or ""
        )

        caption = (
            f"📎 مدرک جدید سفارش #{code}\n\n"
            f"👤 مشتری: {order['full_name']}\n"
            f"📱 موبایل: {order['phone']}\n"
            f"🛠 خدمت: {order['service_name']}\n"
            f"📎 تعداد فایل فعلی: {file_count}\n"
            f"📄 فایل: {file_name}"
        )

        for admin_id in admins:

            try:

                await context.bot.send_document(
                    chat_id=admin_id,
                    document=file_id,
                    caption=caption
                )

            except Exception as e:

                logger.error(
                    "Document delivery error: %s",
                    e
                )

    elif update.message.photo:

        file_id = update.message.photo[-1].file_id

        caption = (
            f"📸 تصویر جدید سفارش #{code}\n\n"
            f"👤 مشتری: {order['full_name']}\n"
            f"📱 موبایل: {order['phone']}\n"
            f"🛠 خدمت: {order['service_name']}\n"
            f"📎 تعداد فایل فعلی: {file_count}"
        )

        for admin_id in admins:

            try:

                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=caption
                )

            except Exception as e:

                logger.error(
                    "Photo delivery error: %s",
                    e
                )


async def send_payment_receipt_to_admins(
    context,
    payment
):

    admins = []

    for admin_id in admin_ids_from_config():
        admins.append(admin_id)

    for admin in db.get_active_admins():

        if admin["user_id"] not in admins:
            admins.append(admin["user_id"])

    for admin_id in admins:

        try:

            if payment["receipt_type"] == "photo":

                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=payment["receipt_file_id"],
                    caption=(
                        f"🧾 رسید پرداخت #{payment['code']}\n"
                        f"💰 مبلغ: {payment['amount']:,} تومان"
                    )
                )

            else:

                await context.bot.send_document(
                    chat_id=admin_id,
                    document=payment["receipt_file_id"],
                    caption=(
                        f"🧾 رسید پرداخت #{payment['code']}\n"
                        f"💰 مبلغ: {payment['amount']:,} تومان"
                    )
                )

        except Exception as e:

            logger.error(
                "Payment receipt delivery error: %s",
                e
            )


# =========================================================
# FINISH ORDER
# =========================================================

async def finish_order(
    query,
    context,
    no_files=False
):

    user = query.from_user

    service_id = context.user_data.get(
        "service_id"
    )

    if not service_id:
        await query.edit_message_text(
            "❌ اطلاعات سفارش پیدا نشد.",
            reply_markup=kb.main_menu()
        )
        return

    service = db.get_service(
        service_id
    )

    if not service:
        await query.edit_message_text(
            "❌ خدمت پیدا نشد.",
            reply_markup=kb.main_menu()
        )
        return

    # اگر فایل قبلاً باعث ساخت سفارش شده، دوباره نساز
    code = context.user_data.get(
        "last_code"
    )

    if not code:

        code = db.create_order(
            user.id,
            service,
            context.user_data["full_name"],
            context.user_data["phone"],
            context.user_data["description"]
        )

    # وضعیت؛ اگر مدارک تکمیلی بوده، سفارش را دوباره در حال بررسی قرار می‌دهیم
    is_extra = bool(context.user_data.get("upload_more"))
    if is_extra:
        db.set_status(code, "reviewing", None, None, "مدارک تکمیلی توسط مشتری ارسال شد")
    else:
        db.set_status(code, "new", None, None, "ثبت نهایی سفارش توسط مشتری")

    order = db.get_order(code)

    file_count = db.get_file_count(
        code
    )

    # اطلاعات سفارش برای ادمین
    await send_admin_message(
        context,
        (
            ("📎 مدارک تکمیلی سفارش دریافت شد\n\n" if is_extra else "🆕 سفارش جدید دریافت شد\n\n") +
            f"📦 شماره سفارش: #{code}\n\n"
            f"👤 نام: {order['full_name']}\n"
            f"📱 موبایل: {order['phone']}\n"
            f"🆔 Telegram ID: {order['user_id']}\n"
            f"🛠 خدمت: {order['service_name']}\n\n"
            f"📝 توضیحات:\n"
            f"{order['description'] or 'ندارد'}\n\n"
            f"📎 تعداد مدارک: {file_count}\n"
            f"📌 وضعیت: {status_name('reviewing' if is_extra else 'new')}"
        ),
        kb.admin_order_buttons(
            code,
            "reviewing" if is_extra else "new"
        )
    )

    # ارسال مجدد همه فایل‌ها
    if file_count:
        await send_order_files_to_admins(
            context,
            code
        )

    clear_order_state(
        context
    )

    await query.edit_message_text(
        f"✅ سفارش شما با موفقیت ثبت شد.\n\n"
        f"📦 شماره سفارش: #{code}\n\n"
        f"📎 تعداد مدارک دریافت‌شده: {file_count}\n\n"
        "سفارش شما برای کارشناسان کافینت ارسال شد. 👨‍💻\n\n"
        "⏳ پس از بررسی، در صورت نیاز به مدارک بیشتر، "
        "مبلغ یا اطلاعات تکمیلی از طریق همین ربات "
        "با شما ارتباط گرفته می‌شود.",
        reply_markup=kb.main_menu()
    )


# =========================================================
# ADMIN STATUS LIST
# =========================================================

async def show_admin_status(
    update,
    status
):

    if status == "all":
        orders = db.get_all_orders()
        title = "📦 همه سفارش‌ها"
    else:
        orders = db.get_orders_by_status(status)
        title = status_name(status)

    if not orders:

        await update.message.reply_text(
            f"{title}\n\n"
            "📭 سفارشی در این بخش وجود ندارد.",
            reply_markup=kb.admin_reply_keyboard()
        )

        return

    rows = []

    for order in orders[:30]:

        rows.append([
            InlineKeyboardButton(
                f"#{order['code']} | {order['service_name'][:25]}",
                callback_data=f"admin_order:{order['code']}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "🔙 پنل مدیریت",
            callback_data="admin_panel"
        )
    ])

    await update.message.reply_text(
        f"{title}\n\n"
        f"تعداد: {len(orders)}",
        reply_markup=InlineKeyboardMarkup(rows)
    )


# =========================================================
# PAY
# =========================================================

async def pay_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    code = query.data.split(":", 1)[1]

    order = db.get_order(
        code,
        query.from_user.id
    )

    if not order:

        await query.edit_message_text(
            "❌ سفارش پیدا نشد.",
            reply_markup=kb.main_menu()
        )
        return

    if not order["amount"]:

        await query.edit_message_text(
            "⚠️ هنوز مبلغ این سفارش مشخص نشده است.",
            reply_markup=kb.back()
        )
        return

    await query.edit_message_text(
        f"💳 پرداخت سفارش #{code}\n\n"
        f"💰 مبلغ:\n"
        f"{order['amount']:,} تومان\n\n"
        f"💳 شماره کارت:\n"
        f"{db.get_card_settings()[0] or CARD_NUMBER}\n"
        f"👤 صاحب کارت: {db.get_card_settings()[1] or '---'}\n\n"
        "لطفاً پس از پرداخت، رسید را در همین چت ارسال کنید.\n\n"
        "📎 رسید می‌تواند عکس یا فایل باشد.",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📎 ارسال رسید پرداخت",
                    callback_data=f"send_receipt:{code}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data=f"detail:{code}"
                ),
                InlineKeyboardButton(
                    "🏠 منوی اصلی",
                    callback_data="main"
                )
            ]
        ])
    )


async def send_receipt_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    code = query.data.split(":", 1)[1]

    order = db.get_order(
        code,
        query.from_user.id
    )

    if not order:
        await query.edit_message_text(
            "❌ سفارش پیدا نشد.",
            reply_markup=kb.main_menu()
        )
        return

    context.user_data["payment_order_code"] = code

    await query.edit_message_text(
        f"🧾 ارسال رسید پرداخت\n\n"
        f"📦 سفارش: #{code}\n"
        f"💰 مبلغ: {order['amount']:,} تومان\n\n"
        "حالا تصویر یا فایل رسید را ارسال کنید.",
        reply_markup=kb.back(f"detail:{code}")
    )


# =========================================================
# SUPPORT REPLY
# =========================================================

async def support_reply_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(
        query.data.split(":", 1)[1]
    )

    context.user_data["admin_action"] = "support_reply"
    context.user_data["support_user_id"] = user_id

    await query.edit_message_text(
        f"💬 پاسخ به کاربر {user_id}\n\n"
        "پیام خود را ارسال کنید:"
    )


# =========================================================
# HANDLE ADMIN SUPPORT REPLY
# =========================================================

async def handle_admin_support_reply(
    update,
    context
):

    user = update.effective_user

    if not is_admin(user.id):
        return False

    action = context.user_data.get(
        "admin_action"
    )

    if action != "support_reply":
        return False

    target_id = context.user_data.get(
        "support_user_id"
    )

    if not target_id:
        return False

    text = update.message.text

    try:

        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "💬 پاسخ پشتیبانی\n\n"
                f"{text}"
            )
        )

        db.save_support_message(
            target_id,
            None,
            "admin_to_user",
            text,
            update.message.message_id
        )

        await update.message.reply_text(
            "✅ پاسخ برای مشتری ارسال شد.",
            reply_markup=kb.admin_reply_keyboard()
        )

    except Exception as e:

        logger.error(
            "Support reply error: %s",
            e
        )

        await update.message.reply_text(
            "❌ ارسال پاسخ انجام نشد."
        )

    context.user_data.pop(
        "admin_action",
        None
    )

    context.user_data.pop(
        "support_user_id",
        None
    )

    return True


# =========================================================
# ROUTER CALLBACK
# =========================================================

async def universal_callback(
    update,
    context
):

    data = update.callback_query.data

    if data.startswith("pay:"):
        await pay_callback(
            update,
            context
        )
        return

    if data.startswith("send_receipt:"):
        await send_receipt_callback(
            update,
            context
        )
        return

    if data.startswith("support_reply:"):
        await support_reply_callback(
            update,
            context
        )
        return

    await callback(
        update,
        context
    )


# =========================================================
# TEXT ROUTER
# =========================================================

async def universal_text(
    update,
    context
):

    if (
        context.user_data.get("admin_action")
        == "support_reply"
    ):

        handled = await handle_admin_support_reply(
            update,
            context
        )

        if handled:
            return

    await text_message(
        update,
        context
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error
    )

    try:

        if update and update.effective_message:

            await update.effective_message.reply_text(
                "❌ خطای موقتی در سیستم رخ داد.\n"
                "لطفاً دوباره تلاش کنید."
            )

    except Exception:
        pass


# =========================================================
# RUN
# =========================================================

def run():

    start_health_server()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            universal_callback
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.ALL,
            file_message
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            universal_text
        )
    )

    app.add_error_handler(
        error_handler
    )

    logger.info(
        "Bot started successfully."
    )

    app.run_polling()


if __name__ == "__main__":
    run()
