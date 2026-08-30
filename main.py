import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import database as db
import keyboards as kb
from config import BOT_TOKEN, ADMIN_IDS, CARD_NUMBER, SUPPORT_INFO
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
db.init_db()


# =========================================================
# Render Health Check
# این بخش فقط برای باز نگه داشتن پورت در Render است.
# منطق ربات تلگرام را تغییر نمی‌دهد.
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info(f"Health server running on port {port}")
    server.serve_forever()


# اجرای سرور Render در یک Thread جدا
health_thread = threading.Thread(
    target=start_health_server,
    daemon=True
)
health_thread.start()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.save_user(update.effective_user)
    context.user_data.clear()
    await update.message.reply_text(
        "🖥️ منوی اصلی\n\nبه کافینت آنلاین خوش آمدید.\n"
        "لطفاً گزینه موردنظر را انتخاب کنید:",
        reply_markup=kb.main_menu()
    )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main":
        context.user_data.clear()
        await query.edit_message_text(
            "🖥️ منوی اصلی",
            reply_markup=kb.main_menu()
        )
        return

    if data == "order":
        await query.edit_message_text(
            "🛒 ثبت سفارش\n\nلطفاً دسته‌بندی خدمت موردنظر خود را انتخاب کنید:",
            reply_markup=kb.category_menu()
        )
        return

    if data.startswith("cat:"):
        category_id = int(data.split(":")[1])
        with db.connect() as database:
            category = database.execute(
                "SELECT * FROM categories WHERE id=?", (category_id,)
            ).fetchone()
        await query.edit_message_text(
            f"{category['emoji']} {category['name']}\n\n"
            "لطفاً خدمت موردنظر را انتخاب کنید:",
            reply_markup=kb.service_menu(category_id)
        )
        return

    if data.startswith("svc:"):
        service = db.get_service(int(data.split(":")[1]))
        context.user_data.update(
            service_id=service["id"],
            stage="name"
        )
        await query.edit_message_text(
            f"{service['emoji']} {service['name']}\n\n"
            "برای ادامه ثبت سفارش، اطلاعات زیر دریافت می‌شود.\n\n"
            "👤 نام و نام خانوادگی خود را ارسال کنید:"
        )
        return

    if data == "myorders":
        orders = db.get_user_orders(query.from_user.id)
        if not orders:
            await query.edit_message_text(
                "📋 هنوز سفارشی ثبت نکرده‌اید.",
                reply_markup=kb.back()
            )
            return

        rows = [
            [__import__("telegram").InlineKeyboardButton(
                f"📦 {o['code']} — {o['service_name']}",
                callback_data=f"detail:{o['code']}"
            )]
            for o in orders[:20]
        ]

        rows.append([
            __import__("telegram").InlineKeyboardButton(
                "🔙 بازگشت", callback_data="main"
            )
        ])

        await query.edit_message_text(
            "📋 سفارش‌های من",
            reply_markup=__import__("telegram").InlineKeyboardMarkup(rows)
        )
        return

    if data.startswith("detail:"):
        order = db.get_order(data.split(":")[1], query.from_user.id)

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

    if data == "prices":
        await query.edit_message_text(
            "💰 تعرفه خدمات\n\n"
            "📌 هزینه بعضی خدمات پس از بررسی مدارک و نوع درخواست اعلام می‌شود.",
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


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stage = context.user_data.get("stage")

    if stage == "name":
        context.user_data["full_name"] = update.message.text
        context.user_data["stage"] = "phone"
        await update.message.reply_text(
            "📱 شماره موبایل خود را ارسال کنید."
        )
        return

    if stage == "phone":
        context.user_data["phone"] = update.message.text
        context.user_data["stage"] = "description"
        await update.message.reply_text(
            "📝 توضیحات سفارش را ارسال کنید."
        )
        return

    if stage == "description":
        context.user_data["description"] = update.message.text
        context.user_data["stage"] = "file"
        await update.message.reply_text(
            "📎 اگر مدرک یا فایل دارید ارسال کنید؛ "
            "اگر ندارید «ندارم» بنویسید."
        )
        return

    if stage == "file":
        if update.message.text.strip() == "ندارم":
            await finish_order(update, context)
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


async def file_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("stage") != "file":
        return

    await finish_order(update, context)

    code = context.user_data.get("last_code")

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


async def finish_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = db.get_service(context.user_data["service_id"])

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


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    await update.message.reply_text(
        "👨‍💻 پنل مدیریت\n\n"
        "📦 سفارش‌ها\n💳 پرداخت‌ها\n"
        "🔄 سفارش‌های در حال انجام\n"
        "✅ سفارش‌های تکمیل‌شده\n"
        "⚙️ تنظیمات"
    )


def run():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CallbackQueryHandler(callback))

    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        file_message
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_message
    ))

    app.run_polling()


if __name__ == "__main__":
    run()
