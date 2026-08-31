import sqlite3
from pathlib import Path
from config import DB_PATH


def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            completed_at TEXT,
            admin_id INTEGER
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
            status TEXT DEFAULT 'pending',
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

        CREATE INDEX IF NOT EXISTS idx_orders_status
        ON orders(status);

        CREATE INDEX IF NOT EXISTS idx_orders_user
        ON orders(user_id);

        CREATE INDEX IF NOT EXISTS idx_files_order
        ON files(order_id);

        CREATE INDEX IF NOT EXISTS idx_messages_order
        ON messages(order_id);
        """)

        # افزودن ستون‌ها به دیتابیس‌های قدیمی
        existing_columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(orders)").fetchall()
        }

        if "started_at" not in existing_columns:
            db.execute("ALTER TABLE orders ADD COLUMN started_at TEXT")

        if "completed_at" not in existing_columns:
            db.execute("ALTER TABLE orders ADD COLUMN completed_at TEXT")

        if "admin_id" not in existing_columns:
            db.execute("ALTER TABLE orders ADD COLUMN admin_id INTEGER")

        # دسته‌بندی‌های اولیه
        if db.execute(
            "SELECT COUNT(*) FROM categories"
        ).fetchone()[0] == 0:

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
            "SELECT * FROM categories ORDER BY sort_order"
        ).fetchall()


def services(category_id):
    with connect() as db:
        return db.execute(
            """
            SELECT * FROM services
            WHERE category_id=?
            ORDER BY id
            """,
            (category_id,)
        ).fetchall()


def get_service(service_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM services WHERE id=?",
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
                description
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                "TEMP",
                user_id,
                service["id"],
                service["name"],
                full_name,
                phone,
                description
            )
        )

        order_id = cur.lastrowid

        code = f"CN-{1000 + order_id}"

        db.execute(
            """
            UPDATE orders
            SET code=?
            WHERE id=?
            """,
            (code, order_id)
        )

        return code


def add_file(
    code,
    file_id,
    file_type,
    file_name=""
):
    with connect() as db:

        order = db.execute(
            "SELECT id FROM orders WHERE code=?",
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
                "SELECT * FROM orders WHERE code=?",
                (code,)
            ).fetchone()

        return db.execute(
            """
            SELECT *
            FROM orders
            WHERE code=? AND user_id=?
            """,
            (code, user_id)
        ).fetchone()


def get_all_orders(limit=30):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM orders
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()


def get_orders_by_status(status, limit=30):
    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM orders
            WHERE status=?
            ORDER BY id ASC
            LIMIT ?
            """,
            (status, limit)
        ).fetchall()


def start_order(code, admin_id):
    with connect() as db:
        db.execute(
            """
            UPDATE orders
            SET status='processing',
                started_at=CURRENT_TIMESTAMP,
                admin_id=?
            WHERE code=?
            """,
            (admin_id, code)
        )


def set_status(code, status):
    with connect() as db:

        if status == "completed":
            db.execute(
                """
                UPDATE orders
                SET status=?,
                    completed_at=CURRENT_TIMESTAMP
                WHERE code=?
                """,
                (status, code)
            )
        else:
            db.execute(
                """
                UPDATE orders
                SET status=?
                WHERE code=?
                """,
                (status, code)
            )


def set_amount(code, amount):
    with connect() as db:
        db.execute(
            """
            UPDATE orders
            SET amount=?,
                status='waiting_payment'
            WHERE code=?
            """,
            (amount, code)
        )


def add_message(
    code,
    sender_type,
    sender_id,
    message_type="text",
    text=None,
    telegram_file_id=None,
    file_name=None
):
    with connect() as db:

        order = db.execute(
            "SELECT id FROM orders WHERE code=?",
            (code,)
        ).fetchone()

        if not order:
            return False

        db.execute(
            """
            INSERT INTO messages
            (
                order_id,
                sender_type,
                sender_id,
                message_type,
                text,
                telegram_file_id,
                file_name
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                order["id"],
                sender_type,
                sender_id,
                message_type,
                text,
                telegram_file_id,
                file_name
            )
        )

        return True


def get_messages(code, limit=50):
    with connect() as db:
        return db.execute(
            """
            SELECT m.*
            FROM messages m
            JOIN orders o ON o.id=m.order_id
            WHERE o.code=?
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (code, limit)
        ).fetchall()
