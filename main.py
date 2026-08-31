import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import database as db
import keyboards as kb

from config import BOT_TOKEN, ADMIN_IDS, CARD_NUMBER, SUPPORT_INFO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
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
        port = int(os.environ.get("PORT", 10000))

        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler
        )

        logger.info(
            f"RENDER HEALTH SERVER STARTED ON PORT {port}"
        )

        server.serve_forever()

    except Exception:
        logger.exception("RENDER HEALTH SERVER ERROR")


health_thread = threading.Thread(
    target=start_health_server,
    daemon=True
)

health_thread.start()


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

    db.save_user(update.effective_user)

    context.user_data.clear()

    await update.message.reply_text(
        "🖥️ منوی اصلی\n\n"
        "به کافینت آنلاین خوش آمدید.\n"
        "لطفاً گزینه موردنظر را انتخاب کنید:",
        reply_markup=kb.main_menu()
    )


# =========================================================
# CALLBACK HANDLER
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
        # MAIN MENU
        # =================================================

        if data == "main":

            context.user_data.clear()

            await query.edit_message_text(
                "🖥️ منوی اصلی",
                reply_markup=kb.main_menu()
            )

            return


        # =================================================
        # REGISTER ORDER
        # =================================================

        if data == "order":

            await query.edit_message_text(
                "🛒 ثبت سفارش\n\n"
                "لطفاً دسته‌بندی خدمت موردنظر خود را انتخاب کنید:",
                reply_markup=kb.category_menu()
            )

            return


        # =================================================
        # CATEGORY
        # =================================================

        if data.startswith("cat:"):

            category_id = int(
                data.split(":")[1]
            )

            logger.info(
                f"CATEGORY SELECTED: {category_id}"
            )

            with db.connect() as database:

                category = database.execute(
                    "SELECT * FROM categories WHERE id=?",
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
                reply_markup=kb.service_menu(category_id)
            )

            return


        # =================================================
        # SERVICE
        # =================================================

        if data.startswith("svc:"):

            service_id = int(
                data.split(":")[1]
            )

            logger.info(
                f"SERVICE SELECTED: {service_id}"
            )

            service = db.get_service(
                service_id
            )


            if not service:

                await query.edit_message_text(
                    "❌ خدمت موردنظر پیدا نشد.",
                    reply_markup=kb.back("order")
                )

                return


            context.user_data.update(
                service_id=service["id"],
                stage="name"
            )


            await query.edit_message_text(
                f"{service['emoji']} "
                f"{service['name']}\n\n"
                "برای ادامه ثبت سفارش، اطلاعات زیر "
                "دریافت می‌شود.\n\n"
                "👤 نام و نام خانوادگی خود را ارسال کنید:"
            )

            return


        # =================================================
        # MY ORDERS
        # =================================================

        if data == "myorders":

            logger.info("MY ORDERS SELECTED")

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
                reply_markup=InlineKeyboardMarkup(rows)
            )

            return


        # =================================================
        # ORDER DETAIL
        # =================================================

        if data.startswith("detail:"):

            code = data.split(":")[1]

            logger.info(
                f"ORDER DETAIL: {code}"
            )

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
                f"وضعیت: {order['status']}",
                reply_markup=kb.back("myorders")
            )

            return


        # =================================================
        # PRICES
        # =================================================

        if data == "prices":

            await query.edit_message_text(
                "💰 تعرفه خدمات\n\n"
                "📌 هزینه بعضی خدمات پس از بررسی "
                "مدارک و نوع درخواست اعلام می‌شود.",
                reply_markup=kb.back()
            )

            return


        # =================================================
        # HELP
        # =================================================

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


        # =================================================
        # SUPPORT
        # =================================================

        if data == "support":

            await query.edit_message_text(
                f"📞 پشتیبانی\n\n{SUPPORT_INFO}",
                reply_markup=kb.back()
            )

            return


        # =================================================
        # UNKNOWN CALLBACK
        # =================================================

        logger.warning(
            f"UNKNOWN CALLBACK DATA: {data}"
        )


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

            logger.exception(
                "FAILED TO SEND CALLBACK ERROR MESSAGE"
            )


# =========================================================
# TEXT MESSAGE
# =========================================================

async def text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    stage = context.user_data.get("stage")

    logger.info(
        f"TEXT MESSAGE | "
        f"user={update.effective_user.id} | "
        f"stage={stage}"
    )


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

        await update.message.reply_text(
            "📎 اگر مدرک یا فایل دارید ارسال کنید؛ "
            "اگر ندارید «ندارم» بنویسید."
        )

        return


    if stage == "file":

        if update.message.text.strip() == "ندارم":

            await finish_order(
                update,
                context
            )

        else:

            await update.message.reply_text(
                "لطفاً فایل یا عکس را ارسال کنید؛ "
                "یا «ندارم» بنویسید."
            )

        return


    await update.message.reply_text(
        "لطفاً از منوی بات استفاده کنید.",
        reply_markup=kb.main_menu()
    )


# =========================================================
# FILE MESSAGE
# =========================================================

async def file_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if context.user_data.get("stage") != "file":
        return


    await finish_order(
        update,
        context
    )


    code = context.user_data.get(
        "last_code"
    )


    if code:

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


    context.user_data.clear()

    context.user_data["last_code"] = code


    await update.message.reply_text(
        f"✅ سفارش شما ثبت شد.\n\n"
        f"📦 شماره سفارش: #{code}\n"
        "⏳ مبلغ پس از بررسی اعلام می‌شود.",
        reply_markup=kb.main_menu()
    )


# =========================================================
# ADMIN
# =========================================================

async def admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id not in ADMIN_IDS:
        return


    await update.message.reply_text(
        "👨‍💻 پنل مدیریت\n\n"
        "📦 سفارش‌ها\n"
        "💳 پرداخت‌ها\n"
        "🔄 سفارش‌های در حال انجام\n"
        "✅ سفارش‌های تکمیل‌شده\n"
        "⚙️ تنظیمات"
    )


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


    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # INLINE BUTTONS
    # -----------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            callback
        )
    )


    # -----------------------------------------------------
    # FILES / PHOTOS
    # -----------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.ALL,
            file_message
        )
    )


    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_message
        )
    )


    logger.info(
        "TELEGRAM BOT POLLING STARTED"
    )


    # دریافت صریح پیام‌ها و Callback Query ها
    app.run_polling(
        allowed_updates=[
            "message",
            "callback_query"
        ]
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    run()
