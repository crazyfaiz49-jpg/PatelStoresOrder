import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
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
            """
        )
        for column_name, column_def in PRODUCT_COLUMN_DEFS.items():
            ensure_column(connection, 'products', column_name, column_def)
        for column_name, column_def in SETTINGS_COLUMN_DEFS.items():
            ensure_column(connection, 'settings', column_name, column_def)
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
