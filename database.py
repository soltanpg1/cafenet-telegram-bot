import sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from config import DB_PATH

TEHRAN = ZoneInfo("Asia/Tehran")

def now_tehran():
    return datetime.now(TEHRAN).strftime("%Y-%m-%d %H:%M:%S")

def today_tehran():
    return datetime.now(TEHRAN).strftime("%Y-%m-%d")


def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _add_column(db, table, column, definition):
    columns = [
        row["name"]
        for row in db.execute(f"PRAGMA table_info({table})").fetchall()
    ]

    if column not in columns:
        db.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            full_name TEXT,
            phone TEXT,
            description TEXT,
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            telegram_file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            receipt_file_id TEXT NOT NULL,
            receipt_type TEXT DEFAULT 'document',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'admin',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            message_type TEXT DEFAULT 'text',
            text TEXT,
            telegram_file_id TEXT,
            file_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_code TEXT,
            direction TEXT NOT NULL,
            message TEXT,
            telegram_message_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT,
            admin_id INTEGER,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS admin_quotas (
            admin_id INTEGER PRIMARY KEY,
            daily_limit INTEGER NOT NULL DEFAULT 0
        );
        """)

        # Migration برای دیتابیس قبلی
        _add_column(db, "orders", "admin_id", "INTEGER")
        _add_column(db, "orders", "admin_name", "TEXT")
        _add_column(db, "orders", "updated_at", "TEXT")
        _add_column(db, "orders", "started_at", "TEXT")
        _add_column(db, "orders", "completed_at", "TEXT")
        _add_column(db, "orders", "rejection_reason", "TEXT")
        _add_column(db, "payments", "receipt_type", "TEXT DEFAULT 'document'")

        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('daily_capacity','0')")
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('card_number','')")
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('card_holder','')")

        if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            categories = [
                ("خدمات دولتی", "🏛", 1),
                ("خدمات دانشگاهی و آموزشی", "🎓", 2),
                ("ثبت‌نام سامانه‌ها", "📝", 3),
                ("خدمات اداری و اینترنتی", "📄", 4),
                ("چاپ و تبدیل فایل", "🖨", 5),
                ("دریافت و تکمیل فرم", "📑", 6),
                ("پیگیری درخواست‌ها", "🔎", 7),
                ("سایر خدمات", "➕", 8),
            ]

            db.executemany(
                """
                INSERT INTO categories(name, emoji, sort_order)
                VALUES(?,?,?)
                """,
                categories
            )

            def category_id(name):
                return db.execute(
                    "SELECT id FROM categories WHERE name=?",
                    (name,)
                ).fetchone()["id"]

            services = [
                (category_id("خدمات دولتی"), "خدمات کارت ملی و شناسنامه", "🪪"),
                (category_id("خدمات دولتی"), "خدمات ثبت احوال", "📋"),
                (category_id("خدمات دولتی"), "خدمات مربوط به مسکن", "🏠"),
                (category_id("خدمات دولتی"), "خدمات کاری و بیمه‌ای", "💼"),
                (category_id("خدمات دولتی"), "خدمات مالیاتی", "💰"),

                (category_id("خدمات دانشگاهی و آموزشی"), "ثبت‌نام دانشگاه", "📝"),
                (category_id("خدمات دانشگاهی و آموزشی"), "انتخاب واحد", "📚"),
                (category_id("خدمات دانشگاهی و آموزشی"), "دریافت گواهی", "📄"),
                (category_id("خدمات دانشگاهی و آموزشی"), "امور فارغ‌التحصیلی", "🎓"),
                (category_id("خدمات دانشگاهی و آموزشی"), "ثبت‌نام آزمون", "📝"),

                (category_id("ثبت‌نام سامانه‌ها"), "ثبت‌نام سایت‌ها", "🌐"),
                (category_id("ثبت‌نام سامانه‌ها"), "ایجاد حساب کاربری", "👤"),
                (category_id("ثبت‌نام سامانه‌ها"), "بازیابی حساب", "🔐"),
                (category_id("ثبت‌نام سامانه‌ها"), "تأیید شماره موبایل", "📱"),
                (category_id("ثبت‌نام سامانه‌ها"), "تکمیل اطلاعات سامانه", "📝"),

                (category_id("خدمات اداری و اینترنتی"), "تکمیل فرم", "📑"),
                (category_id("خدمات اداری و اینترنتی"), "چاپ و آماده‌سازی فایل", "🖨"),
                (category_id("خدمات اداری و اینترنتی"), "تبدیل PDF / Word", "📄"),
                (category_id("خدمات اداری و اینترنتی"), "اسکن و آماده‌سازی مدارک", "📸"),
                (category_id("خدمات اداری و اینترنتی"), "ارسال ایمیل", "📧"),

                (category_id("چاپ و تبدیل فایل"), "چاپ سیاه‌وسفید", "🖨"),
                (category_id("چاپ و تبدیل فایل"), "چاپ رنگی", "🖨"),
                (category_id("چاپ و تبدیل فایل"), "تبدیل فایل", "📄"),
                (category_id("چاپ و تبدیل فایل"), "ادغام فایل‌ها", "📑"),
                (category_id("چاپ و تبدیل فایل"), "کاهش حجم فایل", "📦"),
                (category_id("چاپ و تبدیل فایل"), "ویرایش و آماده‌سازی فایل", "📝"),

                (category_id("دریافت و تکمیل فرم"), "دریافت و تکمیل فرم", "📑"),
            ]

            db.executemany(
                """
                INSERT INTO services(category_id,name,emoji)
                VALUES(?,?,?)
                """,
                services
            )


def save_user(user):
    with connect() as db:
        db.execute(
            """
            INSERT INTO users(id, username, full_name)
            VALUES(?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name
            """,
            (
                user.id,
                user.username,
                user.full_name
            )
        )


def categories():
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM categories
            ORDER BY sort_order
            """
        ).fetchall()


def services(category_id):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM services
            WHERE category_id=?
            ORDER BY id
            """,
            (category_id,)
        ).fetchall()


def get_service(service_id):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM services
            WHERE id=?
            """,
            (service_id,)
        ).fetchone()


def _jalali_date(gy, gm, gd):
    gdm=[0,31,28,31,30,31,30,31,31,30,31,30,31]
    gy2=gy-1600; gm2=gm-1; gd2=gd-1
    g=365*gy2+(gy2+3)//4-(gy2+99)//100+(gy2+399)//400
    for i in range(gm2): g += gdm[i+1]
    if gm2>1 and ((gy%4==0 and gy%100!=0) or gy%400==0): g+=1
    g+=gd2; j=g-79; np=j//12053; j%=12053
    jy=979+33*np+4*(j//1461); j%=1461
    if j>=366: jy+=(j-1)//365; j=(j-1)%365
    if j<186: jm=1+j//31; jd=1+j%31
    else: jm=7+(j-186)//30; jd=1+(j-186)%30
    return jy,jm,jd

def create_order(
    user_id,
    service,
    full_name,
    phone,
    description
):
    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO orders
            (
                code,
                user_id,
                service_id,
                service_name,
                full_name,
                phone,
                description,
                status
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                "TEMP",
                user_id,
                service["id"],
                service["name"],
                full_name,
                phone,
                description,
                "new"
            )
        )

        order_id = cur.lastrowid
        now = datetime.now(TEHRAN)
        # Persian season prefix: BH spring, TA summer, PZ autumn, ZM winter
        _, jm, _ = _jalali_date(now.year, now.month, now.day)
        prefix = {1:"BH",2:"BH",3:"BH",4:"TA",5:"TA",6:"TA",7:"PZ",8:"PZ",9:"PZ",10:"ZM",11:"ZM",12:"ZM"}[jm]
        code = f"{prefix}-{1000 + order_id}"

        created_at = now_tehran()
        db.execute(
            """
            UPDATE orders
            SET code=?, created_at=?, updated_at=?
            WHERE id=?
            """,
            (code, created_at, created_at, order_id)
        )

        db.execute(
            """
            INSERT INTO order_history
            (order_id,status,description)
            VALUES(?,?,?)
            """,
            (
                order_id,
                "new",
                "سفارش توسط مشتری ثبت شد"
            )
        )

        return code


def add_file(code, file_id, file_type, file_name=""):
    with connect() as db:
        order = db.execute(
            """
            SELECT id
            FROM orders
            WHERE code=?
            """,
            (code,)
        ).fetchone()

        if not order:
            return False

        db.execute(
            """
            INSERT INTO files
            (
                order_id,
                telegram_file_id,
                file_type,
                file_name
            )
            VALUES(?,?,?,?)
            """,
            (
                order["id"],
                file_id,
                file_type,
                file_name
            )
        )

        return True


def get_order_files(code):
    with connect() as db:
        return db.execute(
            """
            SELECT f.*
            FROM files f
            JOIN orders o ON o.id=f.order_id
            WHERE o.code=?
            ORDER BY f.id
            """,
            (code,)
        ).fetchall()


def get_file_count(code):
    with connect() as db:
        row = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM files f
            JOIN orders o ON o.id=f.order_id
            WHERE o.code=?
            """,
            (code,)
        ).fetchone()

        return row["count"]


def get_user_orders(user_id):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM orders
            WHERE user_id=?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()


def get_order(code, user_id=None):
    with connect() as db:
        if user_id is None:
            return db.execute(
                """
                SELECT
                    o.*,
                    u.username AS username
                FROM orders o
                LEFT JOIN users u
                    ON u.id=o.user_id
                WHERE o.code=?
                """,
                (code,)
            ).fetchone()

        return db.execute(
            """
            SELECT
                o.*,
                u.username AS username
            FROM orders o
            LEFT JOIN users u
                ON u.id=o.user_id
            WHERE o.code=? AND o.user_id=?
            """,
            (code, user_id)
        ).fetchone()


def get_orders_by_status(status):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM orders
            WHERE status=?
            ORDER BY id ASC
            """,
            (status,)
        ).fetchall()


def get_all_orders():
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM orders
            ORDER BY id DESC
            """
        ).fetchall()


def set_status(code, status, admin_id=None, admin_name=None, description=""):
    with connect() as db:
        order = db.execute("SELECT id, status FROM orders WHERE code=?", (code,)).fetchone()
        if not order:
            return False

        now = now_tehran()
        completed_at = now if status == "completed" else None
        started_at = now if status == "in_progress" and order["status"] != "in_progress" else None

        fields = ["status=?", "updated_at=?"]
        values = [status, now]
        if admin_id is not None:
            fields += ["admin_id=?", "admin_name=?"]
            values += [admin_id, admin_name]
        if started_at:
            fields.append("started_at=?"); values.append(started_at)
        if completed_at:
            fields.append("completed_at=?"); values.append(completed_at)
        values.append(code)
        db.execute(f"UPDATE orders SET {', '.join(fields)} WHERE code=?", values)

        db.execute("INSERT INTO order_history(order_id,status,admin_id,description,created_at) VALUES(?,?,?,?,?)",
                   (order["id"], status, admin_id, description, now))
        return True


def assign_order(code, admin_id, admin_name):
    with connect() as db:
        current = db.execute("SELECT id, admin_id FROM orders WHERE code=?", (code,)).fetchone()
        if not current:
            return False, "not_found"
        if current["admin_id"] is not None:
            return False, "already_assigned"

        quota = get_admin_daily_limit(admin_id)
        if quota > 0:
            used = db.execute(
                "SELECT COUNT(*) FROM orders WHERE admin_id=? AND substr(created_at,1,10)=?",
                (admin_id, today_tehran())
            ).fetchone()[0]
            if used >= quota:
                return False, "quota_full"

        now = now_tehran()
        db.execute("UPDATE orders SET admin_id=?, admin_name=?, status='in_progress', started_at=?, updated_at=? WHERE code=?",
                   (admin_id, admin_name, now, now, code))
        db.execute("INSERT INTO order_history(order_id,status,admin_id,description,created_at) VALUES(?,?,?,?,?)",
                   (current["id"], "in_progress", admin_id, f"سفارش توسط {admin_name} پذیرفته شد", now))
        return True, "ok"


def set_amount(code, amount, admin_id=None, admin_name=None):
    with connect() as db:
        order = db.execute(
            """
            SELECT id
            FROM orders
            WHERE code=?
            """,
            (code,)
        ).fetchone()

        if not order:
            return False

        db.execute(
            """
            UPDATE orders
            SET amount=?,
                status='waiting_payment',
                updated_at=?
            WHERE code=?
            """,
            (
                amount,
                now_tehran(),
                code
            )
        )

        db.execute(
            """
            INSERT INTO order_history
            (
                order_id,
                status,
                admin_id,
                description
            )
            VALUES(?,?,?,?)
            """,
            (
                order["id"],
                "waiting_payment",
                admin_id,
                f"مبلغ {amount:,} تومان تعیین شد"
            )
        )

        return True


def add_payment(code, amount, receipt_file_id, receipt_type):
    with connect() as db:
        order = db.execute(
            """
            SELECT id
            FROM orders
            WHERE code=?
            """,
            (code,)
        ).fetchone()

        if not order:
            return False

        db.execute(
            """
            INSERT INTO payments
            (
                order_id,
                amount,
                receipt_file_id,
                receipt_type,
                status
            )
            VALUES(?,?,?,?,?)
            """,
            (
                order["id"],
                amount,
                receipt_file_id,
                receipt_type,
                "pending"
            )
        )

        return True


def get_pending_payment(code):
    with connect() as db:
        return db.execute(
            """
            SELECT p.*, o.code
            FROM payments p
            JOIN orders o ON o.id=p.order_id
            WHERE o.code=? AND p.status='pending'
            ORDER BY p.id DESC
            LIMIT 1
            """,
            (code,)
        ).fetchone()


def update_payment(payment_id, status):
    with connect() as db:
        db.execute(
            """
            UPDATE payments
            SET status=?
            WHERE id=?
            """,
            (
                status,
                payment_id
            )
        )


def set_payment_status_and_order(payment_id, status):
    with connect() as db:
        payment = db.execute(
            """
            SELECT order_id
            FROM payments
            WHERE id=?
            """,
            (payment_id,)
        ).fetchone()

        if not payment:
            return None

        db.execute(
            """
            UPDATE payments
            SET status=?
            WHERE id=?
            """,
            (
                status,
                payment_id
            )
        )

        return payment["order_id"]


def get_order_by_id(order_id):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM orders
            WHERE id=?
            """,
            (order_id,)
        ).fetchone()


def add_admin(user_id, username, full_name, role="admin"):
    with connect() as db:
        db.execute(
            """
            INSERT INTO admins
            (
                user_id,
                username,
                full_name,
                role,
                active
            )
            VALUES(?,?,?,?,1)
            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                role=excluded.role,
                active=1
            """,
            (
                user_id,
                username,
                full_name,
                role
            )
        )


def remove_admin(user_id):
    with connect() as db:
        db.execute(
            """
            UPDATE admins
            SET active=0
            WHERE user_id=?
            """,
            (user_id,)
        )


def get_admin(user_id):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM admins
            WHERE user_id=? AND active=1
            """,
            (user_id,)
        ).fetchone()


def get_all_admins():
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM admins
            ORDER BY role DESC, created_at
            """
        ).fetchall()


def get_active_admins():
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM admins
            WHERE active=1
            """
        ).fetchall()


def save_support_message(
    user_id,
    order_code,
    direction,
    message,
    telegram_message_id=None
):
    with connect() as db:
        db.execute(
            """
            INSERT INTO support_messages
            (
                user_id,
                order_code,
                direction,
                message,
                telegram_message_id
            )
            VALUES(?,?,?,?,?)
            """,
            (
                user_id,
                order_code,
                direction,
                message,
                telegram_message_id
            )
        )


def get_support_messages():
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM support_messages
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()


def get_order_history(code):
    with connect() as db:
        return db.execute(
            """
            SELECT h.*, o.code
            FROM order_history h
            JOIN orders o ON o.id=h.order_id
            WHERE o.code=?
            ORDER BY h.id ASC
            """,
            (code,)
        ).fetchall()


# =========================================================
# تنظیمات، ظرفیت، سهمیه و گزارش‌ها
# =========================================================

def get_setting(key, default=""):
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with connect() as db:
        db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def get_daily_capacity():
    try:
        return max(0, int(get_setting("daily_capacity", "0")))
    except (TypeError, ValueError):
        return 0


def set_daily_capacity(limit):
    set_setting("daily_capacity", max(0, int(limit)))


def get_card_settings():
    return get_setting("card_number", ""), get_setting("card_holder", "")


def set_card_settings(card_number=None, card_holder=None):
    if card_number is not None:
        set_setting("card_number", card_number)
    if card_holder is not None:
        set_setting("card_holder", card_holder)


def get_admin_daily_limit(admin_id):
    with connect() as db:
        row = db.execute("SELECT daily_limit FROM admin_quotas WHERE admin_id=?", (admin_id,)).fetchone()
        return int(row["daily_limit"]) if row else 0


def set_admin_daily_limit(admin_id, limit):
    with connect() as db:
        db.execute("INSERT INTO admin_quotas(admin_id,daily_limit) VALUES(?,?) ON CONFLICT(admin_id) DO UPDATE SET daily_limit=excluded.daily_limit", (admin_id, max(0, int(limit))))


def count_orders_today():
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM orders WHERE substr(created_at,1,10)=?", (today_tehran(),)).fetchone()[0]


def capacity_available():
    limit = get_daily_capacity()
    return limit == 0 or count_orders_today() < limit


def count_admin_orders_today(admin_id):
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM orders WHERE admin_id=? AND substr(created_at,1,10)=?", (admin_id, today_tehran())).fetchone()[0]


def status_counts():
    with connect() as db:
        rows = db.execute("SELECT status, COUNT(*) AS count FROM orders GROUP BY status").fetchall()
        return {r["status"]: r["count"] for r in rows}


def _period_start(kind):
    from datetime import timedelta
    now = datetime.now(TEHRAN)
    if kind == "week":
        return (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    if kind == "month":
        return (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    if kind == "year":
        return (now - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
    return now.strftime("%Y-%m-%d %H:%M:%S")


def period_order_count(kind):
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM orders WHERE created_at>=?", (_period_start(kind),)).fetchone()[0]


def status_report():
    counts = status_counts()
    return {
        "new": counts.get("new", 0),
        "reviewing": counts.get("reviewing", 0),
        "in_progress": counts.get("in_progress", 0),
        "waiting_payment": counts.get("waiting_payment", 0),
        "waiting_documents": counts.get("waiting_documents", 0),
        "completed": counts.get("completed", 0),
        "rejected": counts.get("rejected", 0),
        "total": sum(counts.values()),
        "week": period_order_count("week"),
        "month": period_order_count("month"),
        "year": period_order_count("year"),
    }


def get_orders_created_since(days):
    from datetime import timedelta
    since = (datetime.now(TEHRAN) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with connect() as db:
        return db.execute("SELECT * FROM orders WHERE created_at>=? ORDER BY id DESC", (since,)).fetchall()

# سازگاری با نسخه قبلی: پیام‌های مرتبط با سفارش


def start_order(code, admin_id):
    with connect() as db:
        now = now_tehran()
        db.execute("UPDATE orders SET status='in_progress', started_at=?, admin_id=?, updated_at=? WHERE code=?", (now, admin_id, now, code))


def add_message(code, sender_type, sender_id, message_type="text", text=None, telegram_file_id=None, file_name=None):
    with connect() as db:
        order = db.execute("SELECT id FROM orders WHERE code=?", (code,)).fetchone()
        if not order:
            return False
        db.execute("INSERT INTO messages(order_id,sender_type,sender_id,message_type,text,telegram_file_id,file_name,created_at) VALUES(?,?,?,?,?,?,?,?)",
                   (order["id"], sender_type, sender_id, message_type, text, telegram_file_id, file_name, now_tehran()))
        return True

def get_messages(code, limit=50):
    with connect() as db:
        return db.execute("SELECT m.* FROM messages m JOIN orders o ON o.id=m.order_id WHERE o.code=? ORDER BY m.id DESC LIMIT ?", (code, limit)).fetchall()
