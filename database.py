import sqlite3
from pathlib import Path
from config import DB_PATH


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
        """)

        # Migration برای دیتابیس قبلی
        _add_column(db, "orders", "admin_id", "INTEGER")
        _add_column(db, "orders", "admin_name", "TEXT")
        _add_column(db, "orders", "updated_at", "TEXT")
        _add_column(db, "orders", "started_at", "TEXT")
        _add_column(db, "orders", "completed_at", "TEXT")
        _add_column(db, "payments", "receipt_type", "TEXT DEFAULT 'document'")

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
        code = f"CN-{1000 + order_id}"

        db.execute(
            """
            UPDATE orders
            SET code=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (code, order_id)
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
            VALUES(?,?,?,?,?)
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

        if admin_id is not None:
            db.execute(
                """
                UPDATE orders
                SET status=?,
                    admin_id=?,
                    admin_name=?,
                    started_at=CASE WHEN ?='in_progress' AND started_at IS NULL THEN CURRENT_TIMESTAMP ELSE started_at END,
                    completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    updated_at=CURRENT_TIMESTAMP
                WHERE code=?
                """,
                (
                    status,
                    admin_id,
                    admin_name,
                    status,
                    status,
                    code
                )
            )
        else:
            db.execute(
                """
                UPDATE orders
                SET status=?,
                    started_at=CASE WHEN ?='in_progress' AND started_at IS NULL THEN CURRENT_TIMESTAMP ELSE started_at END,
                    completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    updated_at=CURRENT_TIMESTAMP
                WHERE code=?
                """,
                (
                    status,
                    status,
                    status,
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
                status,
                admin_id,
                description
            )
        )

        return True


def assign_order(code, admin_id, admin_name):
    with connect() as db:
        current = db.execute(
            """
            SELECT admin_id
            FROM orders
            WHERE code=?
            """,
            (code,)
        ).fetchone()

        if not current:
            return False, "not_found"

        if current["admin_id"] is not None:
            return False, "already_assigned"

        db.execute(
            """
            UPDATE orders
            SET admin_id=?,
                admin_name=?,
                status='in_progress',
                updated_at=CURRENT_TIMESTAMP
            WHERE code=?
            """,
            (
                admin_id,
                admin_name,
                code
            )
        )

        order = db.execute(
            """
            SELECT id
            FROM orders
            WHERE code=?
            """,
            (code,)
        ).fetchone()

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
                "in_progress",
                admin_id,
                f"سفارش توسط {admin_name} پذیرفته شد"
            )
        )

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
                updated_at=CURRENT_TIMESTAMP
            WHERE code=?
            """,
            (
                amount,
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


# -----------------------------------------------------------------
# سازگاری با نسخه قدیمی: پیام‌های مرتبط با سفارش
# -----------------------------------------------------------------

def add_message(
    order_code,
    sender_type,
    sender_id,
    text=None,
    message_type="text",
    telegram_file_id=None
):
    with connect() as db:
        order = db.execute(
            "SELECT id FROM orders WHERE code=?",
            (order_code,)
        ).fetchone()
        if not order:
            return False

        db.execute(
            """
            INSERT INTO messages
            (order_id, sender_type, sender_id, message_type, text, telegram_file_id)
            VALUES(?,?,?,?,?,?)
            """,
            (
                order["id"],
                sender_type,
                sender_id,
                message_type,
                text,
                telegram_file_id
            )
        )
        return True


def get_messages(order_code):
    with connect() as db:
        return db.execute(
            """
            SELECT m.*, o.code
            FROM messages m
            JOIN orders o ON o.id=m.order_id
            WHERE o.code=?
            ORDER BY m.id ASC
            """,
            (order_code,)
        ).fetchall()


def start_order(code, admin_id=None, admin_name=None):
    """Compatibility helper for the previous database API."""
    return set_status(
        code,
        "in_progress",
        admin_id,
        admin_name,
        "سفارش شروع شد"
    )
