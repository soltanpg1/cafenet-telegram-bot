from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)

import database as db


# =========================
# پنل مشتری
# =========================

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
            ),
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="main"
            )
        ]
    ])


def continue_order():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ ادامه همین سفارش",
                callback_data="continue_order"
            )
        ],
        [
            InlineKeyboardButton(
                "🆕 ثبت سفارش جدید",
                callback_data="new_order"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="main"
            )
        ]
    ])


def file_finished():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تمام شد",
                callback_data="finish_files"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ مدارکی ندارم",
                callback_data="no_files"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="main"
            )
        ]
    ])


# =========================
# پنل مدیریت
# =========================

def admin_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🛒 پنل مشتری", "👨‍💻 پنل مدیریت"],
            ["⚙️ تنظیمات", "📞 پیام‌های پشتیبانی"]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


def admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 همه سفارش‌ها", callback_data="admin_status:all")],
        [
            InlineKeyboardButton("🆕 سفارش‌های جدید", callback_data="admin_status:new"),
            InlineKeyboardButton("🔄 در حال انجام", callback_data="admin_status:in_progress")
        ],
        [
            InlineKeyboardButton("💳 در انتظار پرداخت", callback_data="admin_status:waiting_payment"),
            InlineKeyboardButton("✅ تکمیل‌شده", callback_data="admin_status:completed")
        ],
        [
            InlineKeyboardButton("🔍 در حال بررسی", callback_data="admin_status:under_review"),
            InlineKeyboardButton("❌ رد سفارش", callback_data="admin_status:rejected")
        ],
        [
            InlineKeyboardButton("🔄 تغییر وضعیت سفارش", callback_data="admin_change_status"),
            InlineKeyboardButton("📎 درخواست مدارک بیشتر", callback_data="admin_request_docs")
        ],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")]
    ])


def admin_settings():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 مدیریت ادمین‌ها", callback_data="admin_manage")],
        [InlineKeyboardButton("📊 وضعیت سفارش‌ها و گزارش", callback_data="admin_reports")],
        [InlineKeyboardButton("💳 تغییر شماره کارت", callback_data="change_card")],
        [InlineKeyboardButton("🏷 نام شماره کارت", callback_data="change_card_name")],
        [InlineKeyboardButton("🎯 محدودیت تعداد سفارش روزانه", callback_data="daily_order_limit")],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="admin_panel")]
    ])


def admin_management():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin")],
        [InlineKeyboardButton("👥 لیست ادمین‌ها", callback_data="admin_list")],
        [InlineKeyboardButton("🎯 سهم روزانه ادمین‌ها", callback_data="admin_quotas")],
        [InlineKeyboardButton("➖ حذف ادمین", callback_data="remove_admin")],
        [InlineKeyboardButton("🔙 تنظیمات", callback_data="admin_settings")]
    ])


def admin_order_buttons(code, status):
    rows = []
    if status == "new":
        rows.append([InlineKeyboardButton("▶️ قبول و شروع سفارش", callback_data=f"take:{code}")])
    if status == "in_progress":
        rows.append([InlineKeyboardButton("💰 تعیین مبلغ", callback_data=f"amount:{code}")])
    if status == "waiting_payment":
        rows.append([InlineKeyboardButton("💳 بررسی پرداخت", callback_data=f"payment:{code}")])

    rows.append([
        InlineKeyboardButton("🔄 تغییر وضعیت", callback_data=f"change_status:{code}"),
        InlineKeyboardButton("📎 درخواست مدارک بیشتر", callback_data=f"request_docs:{code}")
    ])
    rows.append([InlineKeyboardButton("💬 پیام به مشتری", callback_data=f"reply:{code}")])

    if status in ("new", "in_progress", "under_review", "waiting_payment"):
        rows.append([InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject_order:{code}")])
    if status == "in_progress":
        rows.append([InlineKeyboardButton("✅ تکمیل سفارش", callback_data=f"complete:{code}")])

    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_status:{status}")])
    return InlineKeyboardMarkup(rows)


def payment_buttons(code, payment_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید پرداخت", callback_data=f"approve_payment:{payment_id}:{code}")],
        [InlineKeyboardButton("❌ رد پرداخت", callback_data=f"reject_payment:{payment_id}:{code}")],
        [InlineKeyboardButton("💬 پیام به مشتری", callback_data=f"reply:{code}")]
    ])


def status_change_menu(code):
    statuses = [
        ("🆕 سفارش جدید", "new"),
        ("🔄 در حال انجام", "in_progress"),
        ("💳 در انتظار پرداخت", "waiting_payment"),
        ("🔍 در حال بررسی", "under_review"),
        ("✅ تکمیل‌شده", "completed"),
        ("❌ رد سفارش", "rejected"),
    ]
    rows = [[InlineKeyboardButton(label, callback_data=f"set_status:{code}:{status}")]
            for label, status in statuses]
    rows.append([InlineKeyboardButton("🔙 سفارش", callback_data=f"admin_order:{code}")])
    return InlineKeyboardMarkup(rows)


def customer_document_button(code):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 ارسال مدارک بیشتر", callback_data=f"send_more_docs:{code}")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main")]
    ])

