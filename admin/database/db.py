import sqlite3
import sys
from pathlib import Path

def _resolve_root_dir() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2]

    candidates = [base, *base.parents]
    best = base
    best_score = -1

    for candidate in candidates:
        score = 0
        if (candidate / 'patelstores.db').exists():
            score += 4
        if (candidate / 'products.json').exists():
            score += 2
        if (candidate / 'images').is_dir():
            score += 2
        if (candidate / 'backup').is_dir():
            score += 1
        if (candidate / '.git').exists():
            score += 2

        if score > best_score:
            best = candidate
            best_score = score

    return best


ROOT_DIR = _resolve_root_dir()
DB_PATH = ROOT_DIR / 'patelstores.db'


PRODUCT_COLUMN_DEFS = {
    'purchase_price': 'REAL DEFAULT 0',
    'selling_price': 'REAL DEFAULT 0',
    'wholesale_price': 'REAL DEFAULT 0',
    'barcode': 'TEXT DEFAULT ""',
    'gst': 'REAL DEFAULT 0',
    'hsn': 'TEXT DEFAULT ""',
    'stock': 'REAL DEFAULT 0',
    'min_stock': 'REAL DEFAULT 0',
}

RETAILER_COLUMN_DEFS = {
    'owner_name': 'TEXT DEFAULT ""',
    'mobile_number': 'TEXT DEFAULT ""',
    'whatsapp_number': 'TEXT DEFAULT ""',
    'address': 'TEXT DEFAULT ""',
    'city': 'TEXT DEFAULT ""',
    'gst_number': 'TEXT DEFAULT ""',
    'credit_limit': 'REAL DEFAULT 0',
    'outstanding_balance': 'REAL DEFAULT 0',
    'status': 'TEXT DEFAULT "Active"',
    'created_at': 'TEXT',
    'updated_at': 'TEXT',
}

ORDER_COLUMN_DEFS = {
    'retailer_id': 'INTEGER DEFAULT 0',
    'order_number': 'TEXT DEFAULT ""',
    'order_date': 'TEXT DEFAULT ""',
    'status': 'TEXT DEFAULT "Pending"',
    'total_amount': 'REAL DEFAULT 0',
    'notes': 'TEXT DEFAULT ""',
    'created_at': 'TEXT',
    'updated_at': 'TEXT',
}

SETTINGS_COLUMN_DEFS = {
    'commit_message': 'TEXT DEFAULT "Update catalog"',
    'website_folder': 'TEXT DEFAULT "."',
    'database_path': 'TEXT DEFAULT "patelstores.db"',
    'theme': 'TEXT DEFAULT "dark"',
}


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_column(connection, table_name: str, column_name: str, column_def: str):
    columns = {
        row['name']
        for row in connection.execute(f'PRAGMA table_info({table_name})').fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}'
        )


def init_db():
    connection = get_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                category TEXT,
                price REAL,
                description TEXT,
                image TEXT,
                purchase_price REAL DEFAULT 0,
                selling_price REAL DEFAULT 0,
                wholesale_price REAL DEFAULT 0,
                barcode TEXT DEFAULT '',
                gst REAL DEFAULT 0,
                hsn TEXT DEFAULT '',
                stock REAL DEFAULT 0,
                min_stock REAL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT
            );

            CREATE TABLE IF NOT EXISTS retailers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_name TEXT,
                owner_name TEXT DEFAULT '',
                mobile_number TEXT DEFAULT '',
                whatsapp_number TEXT DEFAULT '',
                address TEXT DEFAULT '',
                city TEXT DEFAULT '',
                gst_number TEXT DEFAULT '',
                credit_limit REAL DEFAULT 0,
                outstanding_balance REAL DEFAULT 0,
                status TEXT DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_repo TEXT,
                branch TEXT,
                website_url TEXT,
                images_folder TEXT,
                backup_folder TEXT,
                commit_message TEXT DEFAULT 'Update catalog',
                website_folder TEXT DEFAULT '.',
                database_path TEXT DEFAULT 'patelstores.db',
                theme TEXT DEFAULT 'dark'
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                retailer_id INTEGER DEFAULT 0,
                order_number TEXT DEFAULT '',
                order_date TEXT DEFAULT '',
                status TEXT DEFAULT 'Pending',
                total_amount REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_id INTEGER DEFAULT 0,
                product_name TEXT DEFAULT '',
                quantity REAL DEFAULT 0,
                wholesale_price REAL DEFAULT 0,
                line_total REAL DEFAULT 0
            );
            """
        )
        for column_name, column_def in PRODUCT_COLUMN_DEFS.items():
            ensure_column(connection, 'products', column_name, column_def)
        for column_name, column_def in SETTINGS_COLUMN_DEFS.items():
            ensure_column(connection, 'settings', column_name, column_def)
        for column_name, column_def in RETAILER_COLUMN_DEFS.items():
            ensure_column(connection, 'retailers', column_name, column_def)
        for column_name, column_def in ORDER_COLUMN_DEFS.items():
            ensure_column(connection, 'orders', column_name, column_def)
        connection.execute('CREATE INDEX IF NOT EXISTS idx_retailers_shop_name ON retailers(shop_name)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_retailers_mobile_number ON retailers(mobile_number)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_retailers_city ON retailers(city)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_retailers_status ON retailers(status)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_retailers_gst_number ON retailers(gst_number)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_orders_retailer_id ON orders(retailer_id)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_products_name ON products(product_name)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)')
        connection.execute(
            'UPDATE products SET selling_price = COALESCE(NULLIF(selling_price, 0), price, 0)'
        )
        connection.execute(
            'UPDATE products SET price = COALESCE(NULLIF(price, 0), selling_price, 0)'
        )
        connection.commit()
        seed_defaults(connection)
    finally:
        connection.close()


def seed_defaults(connection):
    category_count = connection.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
    if category_count == 0:
        connection.execute('INSERT INTO categories (category_name) VALUES (?)', ('General',))

    settings_count = connection.execute('SELECT COUNT(*) FROM settings').fetchone()[0]
    if settings_count == 0:
        connection.execute(
            'INSERT INTO settings (github_repo, branch, website_url, images_folder, backup_folder, commit_message, website_folder, database_path, theme) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                'PatelStoresOrder',
                'main',
                'https://your-username.github.io/PatelStoresOrder/',
                'images',
                'backup',
                'Update catalog',
                '.',
                'patelstores.db',
                'dark',
            ),
        )

    connection.commit()


init_db()
