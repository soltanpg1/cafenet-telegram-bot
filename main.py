import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import database as db
import keyboards as kb

from config import BOT_TOKEN, ADMIN_IDS, CARD_NUMBER, SUPPORT_INFO

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


# =========================================================
# DATABASE
# =========================================================

db.init_db()


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def start_health_server():

    try:
        port = int(
            os.environ.get("PORT", 10000)
        )

        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler
        )

        logger.info(
            f"HEALTH SERVER STARTED ON PORT {port}"
        )

        server.serve_forever()

    except Exception:
        logger.exception(
            "HEALTH SERVER ERROR"
        )


threading.Thread(
    target=start_health_server,
    daemon=True
).start()


# =========================================================
# HELPERS
# =========================================================

STATUS_NAMES = {
    "new": "🆕 جدید",
    "processing": "🔄 در حال بررسی",
    "waiting_docs": "📎 منتظر مدارک",
    "waiting_payment": "💳 منتظر پرداخت",
    "completed": "✅ تکمیل‌شده",
    "rejected": "❌ ردشده"
}


def status_name(status):
    return STATUS_NAMES.get(
        status,
        status
    )


def is_admin(user_id):
    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.info(
        f"START COMMAND FROM USER: "
        f"{update.effective_user.id}"
    )

    db.save_user(
        update.effective_user
    )

    context.user_data.clear()

    await update.message.reply_text(
        "🖥️ منوی اصلی\n\n"
        "به کافینت آنلاین خوش آمدید.\n"
        "لطفاً گزینه موردنظر را انتخاب کنید:",
        reply_markup=kb.main_menu()
    )


# =========================================================
# ADMIN COMMAND
# =========================================================

async def admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    context.user_data.clear()

    await update.message.reply_text(
        "👨‍💻 پنل مدیریت\n\n"
        "از منوی زیر بخش موردنظر را انتخاب کنید:",
        reply_markup=kb.admin_menu()
    )


# =========================================================
# ORDER TEXT
# =========================================================

async def text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    stage = context.user_data.get(
        "stage"
    )

    logger.info(
        f"TEXT MESSAGE | "
        f"user={user_id} | "
        f"stage={stage}"
    )


    # =====================================================
    # ADMIN REPLY MODE
    # =====================================================

    if is_admin(user_id):

        reply_code = context.user_data.get(
            "admin_reply_order"
        )

        if reply_code:

            text = update.message.text

            order = db.get_order(
                reply_code
            )

            if not order:

                context.user_data.pop(
                    "admin_reply_order",
                    None
                )

                await update.message.reply_text(
                    "❌ سفارش پیدا نشد."
                )

                return


            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"💬 پیام پشتیبانی\n"
                    f"📦 سفارش #{reply_code}\n\n"
                    f"{text}"
                )
            )


            db.add_message(
                reply_code,
                "admin",
                user_id,
                "text",
                text=text
            )


            await update.message.reply_text(
                "✅ پیام برای مشتری ارسال شد.",
                reply_markup=kb.admin_order_buttons(
                    reply_code
                )
            )

            context.user_data.pop(
                "admin_reply_order",
                None
            )

            return


        # درخواست مدرک
        request_code = context.user_data.get(
            "admin_request_file"
        )

        if request_code:

            text = update.message.text

            order = db.get_order(
                request_code
            )

            if order:

                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"📎 درخواست مدرک\n"
                        f"📦 سفارش #{request_code}\n\n"
                        f"{text}"
                    )
                )

                db.add_message(
                    request_code,
                    "admin",
                    user_id,
                    "text",
                    text=text
                )

                db.set_status(
                    request_code,
                    "waiting_docs"
                )

                await update.message.reply_text(
                    "✅ درخواست مدرک برای مشتری ارسال شد."
                )

            context.user_data.pop(
                "admin_request_file",
                None
            )

            return


        # تعیین مبلغ
        amount_code = context.user_data.get(
            "admin_amount_order"
        )

        if amount_code:

            try:
                amount = int(
                    text.replace(",", "")
                    .replace("،", "")
                    .strip()
                )

                if amount <= 0:
                    raise ValueError

            except ValueError:

                await update.message.reply_text(
                    "❌ مبلغ را فقط به صورت عدد وارد کنید.\n"
                    "مثال:\n"
                    "250000"
                )

                return


            order = db.get_order(
                amount_code
            )

            if order:

                db.set_amount(
                    amount_code,
                    amount
                )

                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"💰 مبلغ سفارش شما مشخص شد.\n\n"
                        f"📦 سفارش: #{amount_code}\n"
                        f"💵 مبلغ: {amount:,} تومان\n\n"
                        "لطفاً برای ادامه پرداخت با پشتیبانی در ارتباط باشید."
                    )
                )

                db.add_message(
                    amount_code,
                    "admin",
                    user_id,
                    "text",
                    text=f"مبلغ تعیین شد: {amount:,} تومان"
                )

                await update.message.reply_text(
                    "✅ مبلغ برای مشتری ارسال شد.",
                    reply_markup=kb.admin_order_buttons(
                        amount_code
                    )
                )

            context.user_data.pop(
                "admin_amount_order",
                None
            )

            return


    # =====================================================
    # CUSTOMER ORDER PROCESS
    # =====================================================

    if stage == "name":

        context.user_data["full_name"] = (
            update.message.text
        )

        context.user_data["stage"] = "phone"

        await update.message.reply_text(
            "📱 شماره موبایل خود را ارسال کنید."
        )

        return


    if stage == "phone":

        context.user_data["phone"] = (
            update.message.text
        )

        context.user_data["stage"] = "description"

        await update.message.reply_text(
            "📝 توضیحات سفارش را ارسال کنید."
        )

        return


    if stage == "description":

        context.user_data["description"] = (
            update.message.text
        )

        context.user_data["stage"] = "file"

        context.user_data["pending_files"] = []

        await update.message.reply_text(
            "📎 مدارک یا فایل‌های موردنیاز را ارسال کنید.\n\n"
            "می‌توانید چند فایل یا عکس بفرستید.\n\n"
            "وقتی ارسال مدارک تمام شد، عبارت «تمام شد» را بفرستید.\n"
            "اگر مدرکی ندارید، «ندارم» بنویسید."
        )

        return


    if stage == "file":

        text = update.message.text.strip()

        if text in ["تمام شد", "تموم شد", "تمام", "ندارم"]:

            await finish_order(
                update,
                context
            )

            return


        await update.message.reply_text(
            "📎 لطفاً فایل یا عکس ارسال کنید.\n"
            "بعد از پایان ارسال مدارک، «تمام شد» بنویسید."
        )

        return


    # =====================================================
    # CUSTOMER NORMAL CHAT
    # =====================================================

    await update.message.reply_text(
        "لطفاً از منوی بات استفاده کنید.",
        reply_markup=kb.main_menu()
    )


# =========================================================
# CUSTOMER FILE
# =========================================================

async def file_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    stage = context.user_data.get(
        "stage"
    )

    logger.info(
        f"FILE MESSAGE | "
        f"user={user_id} | "
        f"stage={stage}"
    )


    # =====================================================
    # ADMIN FILE
    # =====================================================

    if is_admin(user_id):

        code = context.user_data.get(
            "admin_reply_order"
        )

        if not code:
            code = context.user_data.get(
                "admin_request_file"
            )

        if code:

            order = db.get_order(
                code
            )

            if not order:
                return


            if update.message.document:

                file_id = update.message.document.file_id
                file_name = (
                    update.message.document.file_name or ""
                )

                await context.bot.send_document(
                    chat_id=order["user_id"],
                    document=file_id,
                    caption=(
                        f"📎 فایل از پشتیبانی\n"
                        f"📦 سفارش #{code}"
                    )
                )

                db.add_message(
                    code,
                    "admin",
                    user_id,
                    "document",
                    telegram_file_id=file_id,
                    file_name=file_name
                )


            elif update.message.photo:

                file_id = (
                    update.message.photo[-1].file_id
                )

                await context.bot.send_photo(
                    chat_id=order["user_id"],
                    photo=file_id,
                    caption=(
                        f"📎 تصویر از پشتیبانی\n"
                        f"📦 سفارش #{code}"
                    )
                )

                db.add_message(
                    code,
                    "admin",
                    user_id,
                    "photo",
                    telegram_file_id=file_id
                )


            await update.message.reply_text(
                "✅ فایل برای مشتری ارسال شد."
            )

            context.user_data.pop(
                "admin_reply_order",
                None
            )

            context.user_data.pop(
                "admin_request_file",
                None
            )

            return


    # =====================================================
    # CUSTOMER ORDER FILE
    # =====================================================

    if stage != "file":
        return


    if update.message.document:

        file_id = update.message.document.file_id

        file_name = (
            update.message.document.file_name or ""
        )

        context.user_data.setdefault(
            "pending_files",
            []
        ).append({
            "file_id": file_id,
            "type": "document",
            "name": file_name
        })

        await update.message.reply_text(
            "✅ فایل دریافت شد.\n"
            "اگر فایل دیگری دارید ارسال کنید؛ "
            "در غیر این صورت «تمام شد» بنویسید."
        )

        return


    if update.message.photo:

        file_id = (
            update.message.photo[-1].file_id
        )

        context.user_data.setdefault(
            "pending_files",
            []
        ).append({
            "file_id": file_id,
            "type": "photo",
            "name": ""
        })

        await update.message.reply_text(
            "✅ تصویر دریافت شد.\n"
            "اگر مدرک دیگری دارید ارسال کنید؛ "
            "در غیر این صورت «تمام شد» بنویسید."
        )

        return


# =========================================================
# FINISH ORDER
# =========================================================

async def finish_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    service = db.get_service(
        context.user_data["service_id"]
    )

    code = db.create_order(
        update.effective_user.id,
        service,
        context.user_data["full_name"],
        context.user_data["phone"],
        context.user_data["description"]
    )


    pending_files = context.user_data.get(
        "pending_files",
        []
    )


    # ذخیره تمام فایل‌ها
    for item in pending_files:

        db.add_file(
            code,
            item["file_id"],
            item["type"],
            item.get("name", "")
        )


    # ذخیره پیام اصلی سفارش
    db.add_message(
        code,
        "customer",
        update.effective_user.id,
        "text",
        text=(
            f"نام: {context.user_data['full_name']}\n"
            f"موبایل: {context.user_data['phone']}\n"
            f"توضیحات: {context.user_data['description']}"
        )
    )


    # پاک کردن اطلاعات موقت
    context.user_data.clear()


    await update.message.reply_text(
        f"✅ سفارش شما با موفقیت ثبت شد.\n\n"
        f"📦 شماره سفارش: #{code}\n"
        "⏳ سفارش شما در صف بررسی قرار گرفت.\n\n"
        "پس از بررسی، نتیجه از طریق همین ربات به شما اطلاع داده می‌شود.",
        reply_markup=kb.main_menu()
    )


    # ارسال سفارش برای ادمین‌ها
    order = db.get_order(code)

    files = db.get_order_files(code)

    admin_text = (
        "🆕 سفارش جدید\n\n"
        f"📦 شماره سفارش: #{order['code']}\n\n"
        f"👤 نام: {order['full_name']}\n"
        f"📱 موبایل: {order['phone']}\n\n"
        f"🛠 خدمت: {order['service_name']}\n\n"
        f"📝 توضیحات:\n{order['description']}\n\n"
        f"📎 تعداد مدارک: {len(files)}\n"
        f"📊 وضعیت: {status_name(order['status'])}\n"
        f"🕐 زمان ثبت: {order['created_at']}"
    )


    for admin_id in ADMIN_IDS:

        try:

            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=kb.admin_order_buttons(code)
            )


            # ارسال فایل‌های سفارش به ادمین
            for file in files:

                if file["file_type"] == "document":

                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=file["telegram_file_id"],
                        caption=(
                            f"📎 مدرک سفارش #{code}\n"
                            f"{file['file_name'] or ''}"
                        )
                    )

                elif file["file_type"] == "photo":

                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=file["telegram_file_id"],
                        caption=(
                            f"📎 مدرک سفارش #{code}"
                        )
                    )


        except Exception:

            logger.exception(
                f"FAILED TO SEND ORDER {code} "
                f"TO ADMIN {admin_id}"
            )


# =========================================================
# ADMIN ORDER LIST
# =========================================================

async def show_admin_orders(
    query,
    status=None
):

    if status:
        orders = db.get_orders_by_status(
            status
        )
    else:
        orders = db.get_all_orders()


    if not orders:

        await query.edit_message_text(
            "📦 سفارشی در این بخش وجود ندارد.",
            reply_markup=kb.admin_menu()
        )

        return


    rows = []

    for order in orders:

        rows.append([
            InlineKeyboardButton(
                f"#{order['code']} | "
                f"{status_name(order['status'])}",
                callback_data=f"adminorder:{order['code']}"
            )
        ])


    rows.append([
        InlineKeyboardButton(
            "🔙 پنل مدیریت",
            callback_data="admin:menu"
        )
    ])


    await query.edit_message_text(
        "📦 لیست سفارش‌ها\n\n"
        "سفارش‌ها به ترتیب زمان ثبت نمایش داده می‌شوند:",
        reply_markup=InlineKeyboardMarkup(rows)
    )


# =========================================================
# ADMIN ORDER DETAIL
# =========================================================

async def show_admin_order(
    query,
    code
):

    order = db.get_order(
        code
    )

    if not order:

        await query.edit_message_text(
            "❌ سفارش پیدا نشد.",
            reply_markup=kb.admin_menu()
        )

        return


    files = db.get_order_files(
        code
    )


    amount = (
        f"{order['amount']:,} تومان"
        if order["amount"]
        else "تعیین نشده"
    )


    text = (
        f"📦 سفارش #{order['code']}\n\n"
        f"👤 مشتری: {order['full_name']}\n"
        f"📱 موبایل: {order['phone']}\n\n"
        f"🛠 خدمت: {order['service_name']}\n\n"
        f"📝 توضیحات:\n{order['description']}\n\n"
        f"📎 مدارک: {len(files)} فایل\n"
        f"💰 مبلغ: {amount}\n"
        f"📊 وضعیت: {status_name(order['status'])}\n"
        f"🕐 ثبت: {order['created_at']}"
    )


    await query.edit_message_text(
        text,
        reply_markup=kb.admin_order_buttons(
            code
        )
    )


# =========================================================
# CALLBACK
# =========================================================

async def callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    logger.info(
        f"CALLBACK RECEIVED | "
        f"user={query.from_user.id} | "
        f"data={query.data}"
    )

    try:

        await query.answer()

        data = query.data


        # =================================================
        # CUSTOMER MAIN
        # =================================================

        if data == "main":

            context.user_data.clear()

            await query.edit_message_text(
                "🖥️ منوی اصلی",
                reply_markup=kb.main_menu()
            )

            return


        # =================================================
        # CUSTOMER ORDER
        # =================================================

        if data == "order":

            await query.edit_message_text(
                "🛒 ثبت سفارش\n\n"
                "لطفاً دسته‌بندی خدمت موردنظر خود را انتخاب کنید:",
                reply_markup=kb.category_menu()
            )

            return


        if data.startswith("cat:"):

            category_id = int(
                data.split(":")[1]
            )

            with db.connect() as database:

                category = database.execute(
                    """
                    SELECT *
                    FROM categories
                    WHERE id=?
                    """,
                    (category_id,)
                ).fetchone()


            if not category:

                await query.edit_message_text(
                    "❌ دسته‌بندی پیدا نشد.",
                    reply_markup=kb.back("order")
                )

                return


            await query.edit_message_text(
                f"{category['emoji']} "
                f"{category['name']}\n\n"
                "لطفاً خدمت موردنظر را انتخاب کنید:",
                reply_markup=kb.service_menu(
                    category_id
                )
            )

            return


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


            context.user_data.update({
                "service_id": service["id"],
                "stage": "name"
            })


            await query.edit_message_text(
                f"{service['emoji']} "
                f"{service['name']}\n\n"
                "👤 نام و نام خانوادگی خود را ارسال کنید:"
            )

            return


        # =================================================
        # MY ORDERS
        # =================================================

        if data == "myorders":

            orders = db.get_user_orders(
                query.from_user.id
            )


            if not orders:

                await query.edit_message_text(
                    "📋 هنوز سفارشی ثبت نکرده‌اید.",
                    reply_markup=kb.back()
                )

                return


            rows = []

            for order in orders[:20]:

                rows.append([
                    InlineKeyboardButton(
                        f"📦 {order['code']} — "
                        f"{order['service_name']}",
                        callback_data=(
                            f"detail:{order['code']}"
                        )
                    )
                ])


            rows.append([
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="main"
                )
            ])


            await query.edit_message_text(
                "📋 سفارش‌های من",
                reply_markup=InlineKeyboardMarkup(
                    rows
                )
            )

            return


        if data.startswith("detail:"):

            code = data.split(":")[1]

            order = db.get_order(
                code,
                query.from_user.id
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


            await query.edit_message_text(
                f"📦 سفارش #{order['code']}\n\n"
                f"خدمت: {order['service_name']}\n"
                f"مبلغ: {amount}\n"
                f"وضعیت: {status_name(order['status'])}",
                reply_markup=kb.back("myorders")
            )

            return


        # =================================================
        # OTHER CUSTOMER BUTTONS
        # =================================================

        if data == "prices":

            await query.edit_message_text(
                "💰 تعرفه خدمات\n\n"
                "📌 هزینه بعضی خدمات پس از بررسی "
                "مدارک و نوع درخواست اعلام می‌شود.",
                reply_markup=kb.back()
            )

            return


        if data == "help":

            await query.edit_message_text(
                "ℹ️ راهنمای استفاده\n\n"
                "🛒 از ثبت سفارش خدمت را انتخاب کنید.\n"
                "📎 مدارک را در جریان سفارش ارسال کنید.\n"
                "📋 سفارش‌های من برای پیگیری است.\n"
                "💳 پس از تعیین مبلغ، پرداخت انجام می‌شود.",
                reply_markup=kb.back()
            )

            return


        if data == "support":

            await query.edit_message_text(
                f"📞 پشتیبانی\n\n{SUPPORT_INFO}",
                reply_markup=kb.back()
            )

            return


        # =================================================
        # ADMIN ACCESS
        # =================================================

        if not is_admin(
            query.from_user.id
        ):
            return


        # =================================================
        # ADMIN MENU
        # =================================================

        if data == "admin:menu":

            await query.edit_message_text(
                "👨‍💻 پنل مدیریت\n\n"
                "بخش موردنظر را انتخاب کنید:",
                reply_markup=kb.admin_menu()
            )

            return


        if data == "admin:orders":

            await show_admin_orders(
                query
            )

            return


        if data == "admin:new":

            await show_admin_orders(
                query,
                "new"
            )

            return


        if data == "admin:processing":

            await show_admin_orders(
                query,
                "processing"
            )

            return


        if data == "admin:payment":

            await show_admin_orders(
                query,
                "waiting_payment"
            )

            return


        if data == "admin:completed":

            await show_admin_orders(
                query,
                "completed"
            )

            return


        if data == "admin:settings":

            await query.edit_message_text(
                "⚙️ تنظیمات\n\n"
                "این بخش در مرحله بعدی تکمیل می‌شود.",
                reply_markup=kb.admin_menu()
            )

            return


        # =================================================
        # ADMIN ORDER DETAIL
        # =================================================

        if data.startswith("adminorder:"):

            code = data.split(":")[1]

            await show_admin_order(
                query,
                code
            )

            return


        # =================================================
        # START ORDER
        # =================================================

        if data.startswith("admstart:"):

            code = data.split(":")[1]

            db.start_order(
                code,
                query.from_user.id
            )

            order = db.get_order(
                code
            )

            if order:

                try:

                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            f"🔄 سفارش #{code} وارد مرحله بررسی شد.\n\n"
                            "کارشناس در حال بررسی درخواست شماست."
                        )
                    )

                except Exception:
                    logger.exception(
                        "FAILED TO NOTIFY CUSTOMER"
                    )


            await show_admin_order(
                query,
                code
            )

            return


        # =================================================
        # ADMIN CHAT
        # =================================================

        if data.startswith("admchat:"):

            code = data.split(":")[1]

            order = db.get_order(
                code
            )

            if not order:

                await query.edit_message_text(
                    "❌ سفارش پیدا نشد.",
                    reply_markup=kb.admin_menu()
                )

                return


            context.user_data[
                "admin_reply_order"
            ] = code


            await query.edit_message_text(
                f"💬 گفتگو با مشتری\n\n"
                f"📦 سفارش #{code}\n\n"
                "پیام متنی خود را ارسال کنید.\n"
                "پیام شما برای همین مشتری ارسال می‌شود.\n\n"
                "برای لغو حالت گفتگو، /admin را بزنید."
            )

            return


        # =================================================
        # REQUEST DOCUMENT
        # =================================================

        if data.startswith("admfile:"):

            code = data.split(":")[1]

            context.user_data[
                "admin_request_file"
            ] = code


            await query.edit_message_text(
                f"📎 درخواست مدرک بیشتر\n\n"
                f"📦 سفارش #{code}\n\n"
                "توضیح دهید چه مدرکی از مشتری می‌خواهید:"
            )

            return


        # =================================================
        # SET AMOUNT
        # =================================================

        if data.startswith("admamount:"):

            code = data.split(":")[1]

            context.user_data[
                "admin_amount_order"
            ] = code


            await query.edit_message_text(
                f"💰 تعیین مبلغ\n\n"
                f"📦 سفارش #{code}\n\n"
                "مبلغ را به تومان و فقط به صورت عدد ارسال کنید.\n\n"
                "مثال:\n"
                "250000"
            )

            return


        # =================================================
        # CHANGE STATUS
        # =================================================

        if data.startswith("admstatus:"):

            code = data.split(":")[1]

            await query.edit_message_text(
                f"🔄 تغییر وضعیت سفارش #{code}",
                reply_markup=kb.admin_status_menu(
                    code
                )
            )

            return


        # =================================================
        # SET STATUS
        # =================================================

        if data.startswith("setstatus:"):

            parts = data.split(":")

            status = parts[1]
            code = parts[2]

            db.set_status(
                code,
                status
            )

            order = db.get_order(
                code
            )


            if order:

                try:

                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            f"📊 وضعیت سفارش شما تغییر کرد.\n\n"
                            f"📦 سفارش: #{code}\n"
                            f"وضعیت جدید: {status_name(status)}"
                        )
                    )

                except Exception:
                    logger.exception(
                        "FAILED TO SEND STATUS"
                    )


            await show_admin_order(
                query,
                code
            )

            return


        # =================================================
        # COMPLETE
        # =================================================

        if data.startswith("admcomplete:"):

            code = data.split(":")[1]

            db.set_status(
                code,
                "completed"
            )

            order = db.get_order(
                code
            )

            if order:

                try:

                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            f"✅ سفارش شما تکمیل شد.\n\n"
                            f"📦 شماره سفارش: #{code}\n\n"
                            "در صورت نیاز به پیگیری، از بخش پشتیبانی استفاده کنید."
                        )
                    )

                except Exception:
                    logger.exception(
                        "FAILED TO NOTIFY COMPLETION"
                    )


            await show_admin_order(
                query,
                code
            )

            return


        # =================================================
        # REJECT
        # =================================================

        if data.startswith("admreject:"):

            code = data.split(":")[1]

            db.set_status(
                code,
                "rejected"
            )

            order = db.get_order(
                code
            )

            if order:

                try:

                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=(
                            f"❌ سفارش #{code} رد شد.\n\n"
                            "برای اطلاع از علت یا پیگیری بیشتر "
                            "با پشتیبانی در ارتباط باشید."
                        )
                    )

                except Exception:
                    logger.exception(
                        "FAILED TO NOTIFY REJECTION"
                    )


            await show_admin_order(
                query,
                code
            )

            return


    except Exception:

        logger.exception(
            f"CALLBACK ERROR | data={query.data}"
        )

        try:

            await query.message.reply_text(
                "❌ هنگام پردازش درخواست مشکلی پیش آمد.\n"
                "لطفاً دوباره تلاش کنید."
            )

        except Exception:
            pass


# =========================================================
# RUN
# =========================================================

def run():

    logger.info(
        "STARTING TELEGRAM BOT..."
    )


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
            callback
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
            text_message
        )
    )


    logger.info(
        "TELEGRAM BOT POLLING STARTED"
    )


    app.run_polling(
        allowed_updates=[
            "message",
            "callback_query"
        ]
    )


if __name__ == "__main__":
    run()
