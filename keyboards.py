from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import database as db


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 ثبت سفارش",
                callback_data="order"
            ),
            InlineKeyboardButton(
                "📋 سفارش‌های من",
                callback_data="myorders"
            ),
        ],
        [
            InlineKeyboardButton(
                "💰 تعرفه خدمات",
                callback_data="prices"
            ),
            InlineKeyboardButton(
                "ℹ️ راهنما",
                callback_data="help"
            ),
        ],
        [
            InlineKeyboardButton(
                "📞 پشتیبانی",
                callback_data="support"
            )
        ],
    ])


def category_menu():
    rows = [
        [
            InlineKeyboardButton(
                f"{c['emoji']} {c['name']}",
                callback_data=f"cat:{c['id']}"
            )
        ]
        for c in db.categories()
    ]

    rows.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main"
        )
    ])

    return InlineKeyboardMarkup(rows)


def service_menu(category_id):
    rows = [
        [
            InlineKeyboardButton(
                f"{s['emoji']} {s['name']}",
                callback_data=f"svc:{s['id']}"
            )
        ]
        for s in db.services(category_id)
    ]

    rows.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="order"
        )
    ])

    return InlineKeyboardMarkup(rows)


def back(callback="main"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data=callback
            )
        ]
    ])


# =========================================================
# ADMIN
# =========================================================

def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📦 همه سفارش‌ها",
                callback_data="admin:orders"
            )
        ],
        [
            InlineKeyboardButton(
                "🆕 سفارش‌های جدید",
                callback_data="admin:new"
            ),
            InlineKeyboardButton(
                "🔄 در حال انجام",
                callback_data="admin:processing"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 در انتظار پرداخت",
                callback_data="admin:payment"
            ),
            InlineKeyboardButton(
                "✅ تکمیل‌شده",
                callback_data="admin:completed"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات",
                callback_data="admin:settings"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 منوی اصلی",
                callback_data="main"
            )
        ]
    ])


def admin_order_buttons(code):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ شروع بررسی",
                callback_data=f"admstart:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "💬 گفتگو با مشتری",
                callback_data=f"admchat:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "📎 درخواست مدرک بیشتر",
                callback_data=f"admfile:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 تعیین مبلغ",
                callback_data=f"admamount:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 تغییر وضعیت",
                callback_data=f"admstatus:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ تکمیل سفارش",
                callback_data=f"admcomplete:{code}"
            ),
            InlineKeyboardButton(
                "❌ رد سفارش",
                callback_data=f"admreject:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 سفارش‌ها",
                callback_data="admin:orders"
            )
        ]
    ])


def admin_status_menu(code):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🆕 جدید",
                callback_data=f"setstatus:new:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 در حال بررسی",
                callback_data=f"setstatus:processing:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "📎 منتظر مدارک",
                callback_data=f"setstatus:waiting_docs:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 منتظر پرداخت",
                callback_data=f"setstatus:waiting_payment:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ تکمیل‌شده",
                callback_data=f"setstatus:completed:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ ردشده",
                callback_data=f"setstatus:rejected:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data=f"adminorder:{code}"
            )
        ]
    ])
