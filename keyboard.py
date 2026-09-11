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
            ["📦 همه سفارش‌ها"],
            ["🆕 سفارش‌های جدید", "🔄 در حال انجام"],
            ["💳 در انتظار پرداخت", "🔍 در حال بررسی"],
            ["📎 منتظر مدارک", "❌ رد شده"],
            ["✅ تکمیل‌شده", "🔄 تغییر وضعیت سفارش"],
            ["📎 درخواست مدارک بیشتر", "💬 پیام‌های پشتیبانی"],
            ["👥 مدیریت ادمین‌ها", "👤 پنل مشتری"],
            ["⚙️ تنظیمات", "👨‍💻 پنل مدیریت"]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


def admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 همه سفارش‌ها", callback_data="admin_status:all")],
        [InlineKeyboardButton("🆕 سفارش‌های جدید", callback_data="admin_status:new"), InlineKeyboardButton("🔄 در حال انجام", callback_data="admin_status:in_progress")],
        [InlineKeyboardButton("💳 در انتظار پرداخت", callback_data="admin_status:waiting_payment"), InlineKeyboardButton("🔍 در حال بررسی", callback_data="admin_status:reviewing")],
        [InlineKeyboardButton("📎 منتظر مدارک", callback_data="admin_status:waiting_documents"), InlineKeyboardButton("❌ رد شده", callback_data="admin_status:rejected")],
        [InlineKeyboardButton("✅ تکمیل‌شده", callback_data="admin_status:completed")],
        [InlineKeyboardButton("🔄 تغییر وضعیت سفارش", callback_data="change_status")],
        [InlineKeyboardButton("📎 درخواست مدارک بیشتر", callback_data="request_docs")],
        [InlineKeyboardButton("👨‍💻 مدیریت پنل", callback_data="admin_manage"), InlineKeyboardButton("💬 پیام‌های پشتیبانی", callback_data="admin_support")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")]
    ])


def admin_order_buttons(code, status):
    rows = []
    if status == "new":
        rows.append([InlineKeyboardButton("🔍 انتقال به در حال بررسی", callback_data=f"review:{code}")])
        rows.append([InlineKeyboardButton("▶️ قبول و شروع سفارش", callback_data=f"take:{code}")])
    if status == "reviewing":
        rows.append([InlineKeyboardButton("▶️ شروع انجام سفارش", callback_data=f"take:{code}")])
    if status == "in_progress":
        rows.append([InlineKeyboardButton("💰 تعیین مبلغ", callback_data=f"amount:{code}")])
    if status == "waiting_payment":
        rows.append([InlineKeyboardButton("💳 بررسی پرداخت", callback_data=f"payment:{code}")])
    if status in ("new", "reviewing", "in_progress", "waiting_documents", "rejected", "waiting_payment"):
        rows.append([InlineKeyboardButton("🔄 تغییر وضعیت", callback_data=f"change_status:{code}")])
    rows.append([InlineKeyboardButton("📎 درخواست مدارک بیشتر", callback_data=f"request_docs:{code}")])
    rows.append([InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject:{code}")])
    rows.append([InlineKeyboardButton("💬 پیام به مشتری", callback_data=f"reply:{code}")])
    if status == "in_progress":
        rows.append([InlineKeyboardButton("✅ تکمیل سفارش", callback_data=f"complete:{code}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_status:{status}")])
    return InlineKeyboardMarkup(rows)


def payment_buttons(code, payment_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تأیید پرداخت",
                callback_data=f"approve_payment:{payment_id}:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ رد پرداخت",
                callback_data=f"reject_payment:{payment_id}:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "💬 پیام به مشتری",
                callback_data=f"reply:{code}"
            )
        ]
    ])


def admin_settings():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 مدیریت ادمین‌ها", callback_data="admin_manage")],
        [InlineKeyboardButton("📊 وضعیت سفارش‌ها", callback_data="settings_status")],
        [InlineKeyboardButton("💳 تغییر شماره کارت", callback_data="set_card_number")],
        [InlineKeyboardButton("👤 تغییر نام صاحب کارت", callback_data="set_card_holder")],
        [InlineKeyboardButton("📈 ظرفیت روزانه کل", callback_data="set_capacity")],
        [InlineKeyboardButton("🎯 سهمیه روزانه ادمین‌ها", callback_data="admin_quotas")],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="admin_panel")]
    ])

def status_change_menu(code):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 جدید", callback_data=f"setstatus:new:{code}"), InlineKeyboardButton("🔍 در حال بررسی", callback_data=f"setstatus:reviewing:{code}")],
        [InlineKeyboardButton("🔄 در حال انجام", callback_data=f"setstatus:in_progress:{code}"), InlineKeyboardButton("💳 در انتظار پرداخت", callback_data=f"setstatus:waiting_payment:{code}")],
        [InlineKeyboardButton("📎 منتظر مدارک", callback_data=f"setstatus:waiting_documents:{code}"), InlineKeyboardButton("❌ رد شده", callback_data=f"reject:{code}")],
        [InlineKeyboardButton("✅ تکمیل‌شده", callback_data=f"setstatus:completed:{code}")],
        [InlineKeyboardButton("🔙 سفارش", callback_data=f"admin_order:{code}")]
    ])

def admin_management():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ افزودن ادمین",
                callback_data="add_admin"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 لیست ادمین‌ها",
                callback_data="admin_list"
            )
        ],
        [
            InlineKeyboardButton(
                "➖ حذف ادمین",
                callback_data="remove_admin"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 پنل مدیریت",
                callback_data="admin_panel"
            )
        ]
    ])
