from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import database as db

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛒 ثبت سفارش", callback_data="order"),
            InlineKeyboardButton("📋 سفارش‌های من", callback_data="myorders"),
        ],
        [
            InlineKeyboardButton("💰 تعرفه خدمات", callback_data="prices"),
            InlineKeyboardButton("ℹ️ راهنما", callback_data="help"),
        ],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")],
    ])

def category_menu():
    rows = [
        [InlineKeyboardButton(
            f"{c['emoji']} {c['name']}", callback_data=f"cat:{c['id']}"
        )]
        for c in db.categories()
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main")])
    return InlineKeyboardMarkup(rows)

def service_menu(category_id):
    rows = [
        [InlineKeyboardButton(
            f"{s['emoji']} {s['name']}", callback_data=f"svc:{s['id']}"
        )]
        for s in db.services(category_id)
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="order")])
    return InlineKeyboardMarkup(rows)

def back(callback="main"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت", callback_data=callback)]
    ])
