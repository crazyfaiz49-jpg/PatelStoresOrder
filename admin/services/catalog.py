import csv
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from openpyxl import Workbook, load_workbook
from PIL import Image

from admin.database.db import DB_PATH, ROOT_DIR, get_connection
from admin.utils.logger import get_logger

logger = get_logger(__name__)
IMAGES_DIR = ROOT_DIR / 'images'
IMAGES_DIR.mkdir(exist_ok=True)
BACKUP_DIR = ROOT_DIR / 'backup'
BACKUP_DIR.mkdir(exist_ok=True)


@dataclass
class ImportReport:
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


def slugify(value: str) -> str:
    import re

    value = re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-')
    return value or 'product'


def normalize_image_value(image_value: Optional[str]) -> str:
    if not image_value:
        return ''
    path = str(image_value).strip()
    if path.startswith('images/'):
        path = path.split('/', 1)[1]
    return Path(path).name


def get_catalog_image_path(image_value: Optional[str]) -> str:
    file_name = normalize_image_value(image_value)
    if not file_name:
        return 'images/placeholder.png'
    return f'images/{file_name}'


def build_image_filename(product_name: str, input_name: str = '') -> str:
    suffix = Path(input_name or '').suffix.lower()
    if suffix not in {'.jpg', '.jpeg', '.png'}:
        suffix = '.jpg'
    if suffix == '.jpeg':
        suffix = '.jpg'
    return f'{slugify(product_name)}{suffix}'


def save_image_from_path(source_path: str, product_name: str) -> str:
    src = Path(source_path)
    if not src.exists() or not src.is_file():
        return ''

    target_name = build_image_filename(product_name, src.name)
    target_path = IMAGES_DIR / target_name
    if target_path.exists():
        target_path = IMAGES_DIR / f"{slugify(product_name)}-{datetime.now().strftime('%H%M%S')}{target_path.suffix}"

    with Image.open(src) as image:
        if target_path.suffix.lower() in {'.jpg', '.jpeg'}:
            image = image.convert('RGB')
        image.thumbnail((800, 800))
        save_args = {'optimize': True}
        if target_path.suffix.lower() in {'.jpg', '.jpeg'}:
            save_args['quality'] = 82
        image.save(target_path, **save_args)

    return target_path.name


def _row_to_product(row) -> Dict:
    product = dict(row)
    product['image_path'] = get_catalog_image_path(product.get('image'))
    return product


def list_products(
    search: str = '',
    category: str = '',
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    stock_mode: str = 'all',
) -> List[Dict]:
    connection = get_connection()
    try:
        query = 'SELECT * FROM products WHERE 1=1'
        params: List = []
        if search:
            query += ' AND (product_name LIKE ? OR category LIKE ? OR barcode LIKE ? OR CAST(selling_price AS TEXT) LIKE ? OR CAST(price AS TEXT) LIKE ?)'
            pattern = f'%{search}%'
            params.extend([pattern, pattern, pattern, pattern, pattern])
        if category and category.lower() != 'all':
            query += ' AND category = ?'
            params.append(category)
        if min_price is not None:
            query += ' AND selling_price >= ?'
            params.append(float(min_price))
        if max_price is not None and max_price > 0:
            query += ' AND selling_price <= ?'
            params.append(float(max_price))
        if stock_mode == 'out':
            query += ' AND stock <= 0'
        elif stock_mode == 'low':
            query += ' AND stock > 0 AND stock <= min_stock'
        elif stock_mode == 'in':
            query += ' AND stock > 0'
        query += ' ORDER BY product_name COLLATE NOCASE ASC'
        rows = connection.execute(query, params).fetchall()
        return [_row_to_product(row) for row in rows]
    finally:
        connection.close()


def get_product(product_id: int) -> Optional[Dict]:
    connection = get_connection()
    try:
        row = connection.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        return _row_to_product(row) if row else None
    finally:
        connection.close()


def list_categories(search: str = '') -> List[Dict]:
    connection = get_connection()
    try:
        if search:
            rows = connection.execute(
                'SELECT * FROM categories WHERE category_name LIKE ? ORDER BY category_name COLLATE NOCASE ASC',
                (f'%{search}%',),
            ).fetchall()
        else:
            rows = connection.execute(
                'SELECT * FROM categories ORDER BY category_name COLLATE NOCASE ASC'
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def ensure_category(name: str):
    category = (name or '').strip()
    if not category:
        return
    connection = get_connection()
    try:
        exists = connection.execute(
            'SELECT id FROM categories WHERE LOWER(category_name) = LOWER(?)', (category,)
        ).fetchone()
        if not exists:
            connection.execute('INSERT INTO categories (category_name) VALUES (?)', (category,))
            connection.commit()
    finally:
        connection.close()


def create_category(name: str):
    ensure_category(name)
    return list_categories()


def rename_category(category_id: int, new_name: str):
    connection = get_connection()
    try:
        row = connection.execute('SELECT category_name FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not row:
            return list_categories()
        old_name = row['category_name']
        new_name_clean = (new_name or '').strip()
        if not new_name_clean:
            return list_categories()
        connection.execute('UPDATE categories SET category_name = ? WHERE id = ?', (new_name_clean, category_id))
        connection.execute('UPDATE products SET category = ? WHERE category = ?', (new_name_clean, old_name))
        connection.commit()
        return list_categories()
    finally:
        connection.close()


def delete_category(category_id: int):
    connection = get_connection()
    try:
        row = connection.execute('SELECT category_name FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not row:
            return list_categories()
        in_use = connection.execute(
            'SELECT COUNT(*) AS cnt FROM products WHERE category = ?', (row['category_name'],)
        ).fetchone()['cnt']
        if in_use > 0:
            raise ValueError('Cannot delete category in use by products.')
        connection.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        connection.commit()
        return list_categories()
    finally:
        connection.close()


def _normalize_payload(payload: Dict) -> Dict:
    selling_price = float(payload.get('selling_price', payload.get('price', 0)) or 0)
    purchase_price = float(payload.get('purchase_price', 0) or 0)
    wholesale_price = float(payload.get('wholesale_price', 0) or 0)
    return {
        'product_name': (payload.get('product_name') or '').strip(),
        'category': (payload.get('category') or 'General').strip() or 'General',
        'purchase_price': purchase_price,
        'selling_price': selling_price,
        'wholesale_price': wholesale_price,
        'barcode': (payload.get('barcode') or '').strip(),
        'description': (payload.get('description') or '').strip(),
        'gst': float(payload.get('gst', 0) or 0),
        'hsn': (payload.get('hsn') or '').strip(),
        'stock': float(payload.get('stock', 0) or 0),
        'min_stock': float(payload.get('min_stock', 0) or 0),
        'image': normalize_image_value(payload.get('image')),
        'price': selling_price,
    }


def create_product(payload: Dict, image_source: str = ''):
    data = _normalize_payload(payload)
    ensure_category(data['category'])
    if image_source:
        data['image'] = save_image_from_path(image_source, data['product_name'])

    now = datetime.now().isoformat(timespec='seconds')
    connection = get_connection()
    try:
        connection.execute(
            '''
            INSERT INTO products (
                product_name, category, price, description, image,
                purchase_price, selling_price, wholesale_price,
                barcode, gst, hsn, stock, min_stock,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data['product_name'],
                data['category'],
                data['price'],
                data['description'],
                data['image'],
                data['purchase_price'],
                data['selling_price'],
                data['wholesale_price'],
                data['barcode'],
                data['gst'],
                data['hsn'],
                data['stock'],
                data['min_stock'],
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    generate_catalog_json()


def _delete_image_if_unused(connection, image_name: str, exclude_id: Optional[int] = None):
    image_name = normalize_image_value(image_name)
    if not image_name:
        return
    query = 'SELECT COUNT(*) AS cnt FROM products WHERE image = ?'
    params: List = [image_name]
    if exclude_id is not None:
        query += ' AND id != ?'
        params.append(exclude_id)
    cnt = connection.execute(query, params).fetchone()['cnt']
    if cnt == 0:
        disk_path = IMAGES_DIR / image_name
        if disk_path.exists() and disk_path.is_file():
            disk_path.unlink()


def update_product(product_id: int, payload: Dict, image_source: str = ''):
    data = _normalize_payload(payload)
    ensure_category(data['category'])
    connection = get_connection()
    try:
        existing = connection.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        if not existing:
            raise ValueError('Product not found.')

        old_image = normalize_image_value(existing['image'])
        data['image'] = data['image'] or old_image
        if image_source:
            data['image'] = save_image_from_path(image_source, data['product_name'])
            _delete_image_if_unused(connection, old_image, exclude_id=product_id)

        connection.execute(
            '''
            UPDATE products
            SET product_name = ?, category = ?, price = ?, description = ?, image = ?,
                purchase_price = ?, selling_price = ?, wholesale_price = ?,
                barcode = ?, gst = ?, hsn = ?, stock = ?, min_stock = ?, updated_at = ?
            WHERE id = ?
            ''',
            (
                data['product_name'],
                data['category'],
                data['price'],
                data['description'],
                data['image'],
                data['purchase_price'],
                data['selling_price'],
                data['wholesale_price'],
                data['barcode'],
                data['gst'],
                data['hsn'],
                data['stock'],
                data['min_stock'],
                datetime.now().isoformat(timespec='seconds'),
                product_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    generate_catalog_json()


def duplicate_product(product_id: int):
    product = get_product(product_id)
    if not product:
        raise ValueError('Product not found.')

    duplicate_name = f"{product['product_name']} Copy"
    payload = {
        'product_name': duplicate_name,
        'category': product['category'],
        'purchase_price': product.get('purchase_price', 0),
        'selling_price': product.get('selling_price', product.get('price', 0)),
        'wholesale_price': product.get('wholesale_price', 0),
        'barcode': '',
        'description': product.get('description', ''),
        'gst': product.get('gst', 0),
        'hsn': product.get('hsn', ''),
        'stock': product.get('stock', 0),
        'min_stock': product.get('min_stock', 0),
        'image': product.get('image', ''),
    }
    create_product(payload)


def delete_product(product_id: int):
    connection = get_connection()
    try:
        row = connection.execute('SELECT image FROM products WHERE id = ?', (product_id,)).fetchone()
        if not row:
            return
        image_name = normalize_image_value(row['image'])
        connection.execute('DELETE FROM products WHERE id = ?', (product_id,))
        _delete_image_if_unused(connection, image_name)
        connection.commit()
    finally:
        connection.close()

    generate_catalog_json()


def generate_catalog_json() -> List[Dict]:
    connection = get_connection()
    try:
        rows = connection.execute('SELECT * FROM products ORDER BY product_name COLLATE NOCASE ASC').fetchall()
    finally:
        connection.close()

    products = []
    for row in rows:
        selling_price = row['selling_price'] if row['selling_price'] is not None else row['price']
        products.append(
            {
                'id': slugify(row['product_name']),
                'name': row['product_name'],
                'category': row['category'] or 'General',
                'price': round(float(selling_price or 0), 2),
                'image': get_catalog_image_path(row['image']),
                'description': row['description'] or '',
            }
        )

    target = ROOT_DIR / 'products.json'
    with open(target, 'w', encoding='utf-8') as handle:
        json.dump({'products': products}, handle, indent=2)
        handle.write('\n')

    return products


def _normalize_header(header: str) -> str:
    import re

    return re.sub(r'[^a-z0-9]+', '', (header or '').strip().lower())


def import_products_from_excel(file_path: str) -> ImportReport:
    workbook = load_workbook(file_path, data_only=True)
    sheet = workbook.active

    headers_raw = [str(cell).strip() if cell is not None else '' for cell in next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))]
    lookup = {_normalize_header(name): idx for idx, name in enumerate(headers_raw)}

    aliases = {
        'product_name': ['productname', 'name', 'itemname'],
        'category': ['category', 'group'],
        'purchase_price': ['purchaseprice', 'buyprice', 'costprice'],
        'selling_price': ['sellingprice', 'price', 'mrp', 'saleprice'],
        'wholesale_price': ['wholesaleprice', 'wholesale'],
        'barcode': ['barcode', 'barcodeno', 'sku'],
        'description': ['description', 'details'],
        'gst': ['gst', 'tax'],
        'hsn': ['hsn', 'hsncode'],
        'stock': ['stock', 'qty', 'quantity'],
        'min_stock': ['minstock', 'minimumstock', 'reorderlevel'],
        'image': ['image', 'photo', 'photofile'],
    }

    def index_of(field: str) -> Optional[int]:
        for alias in aliases[field]:
            if alias in lookup:
                return lookup[alias]
        return None

    idx = {field: index_of(field) for field in aliases}
    if idx['product_name'] is None:
        raise ValueError('Import file must contain Product Name column.')

    connection = get_connection()
    report = ImportReport()
    try:
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            try:
                product_name = str(row[idx['product_name']]).strip() if idx['product_name'] is not None and row[idx['product_name']] is not None else ''
                if not product_name:
                    report.skipped += 1
                    continue

                payload = {
                    'product_name': product_name,
                    'category': str(row[idx['category']]).strip() if idx['category'] is not None and row[idx['category']] is not None else 'General',
                    'purchase_price': float(row[idx['purchase_price']]) if idx['purchase_price'] is not None and row[idx['purchase_price']] not in (None, '') else 0,
                    'selling_price': float(row[idx['selling_price']]) if idx['selling_price'] is not None and row[idx['selling_price']] not in (None, '') else 0,
                    'wholesale_price': float(row[idx['wholesale_price']]) if idx['wholesale_price'] is not None and row[idx['wholesale_price']] not in (None, '') else 0,
                    'barcode': str(row[idx['barcode']]).strip() if idx['barcode'] is not None and row[idx['barcode']] is not None else '',
                    'description': str(row[idx['description']]).strip() if idx['description'] is not None and row[idx['description']] is not None else '',
                    'gst': float(row[idx['gst']]) if idx['gst'] is not None and row[idx['gst']] not in (None, '') else 0,
                    'hsn': str(row[idx['hsn']]).strip() if idx['hsn'] is not None and row[idx['hsn']] is not None else '',
                    'stock': float(row[idx['stock']]) if idx['stock'] is not None and row[idx['stock']] not in (None, '') else 0,
                    'min_stock': float(row[idx['min_stock']]) if idx['min_stock'] is not None and row[idx['min_stock']] not in (None, '') else 0,
                    'image': str(row[idx['image']]).strip() if idx['image'] is not None and row[idx['image']] is not None else '',
                }
                ensure_category(payload['category'])
                key_barcode = payload['barcode']
                existing = None
                if key_barcode:
                    existing = connection.execute('SELECT id FROM products WHERE barcode = ?', (key_barcode,)).fetchone()
                if existing is None:
                    existing = connection.execute(
                        'SELECT id FROM products WHERE LOWER(product_name) = LOWER(?) AND LOWER(category) = LOWER(?)',
                        (payload['product_name'], payload['category']),
                    ).fetchone()

                if existing:
                    data = _normalize_payload(payload)
                    connection.execute(
                        '''
                        UPDATE products
                        SET product_name = ?, category = ?, price = ?, description = ?, image = ?,
                            purchase_price = ?, selling_price = ?, wholesale_price = ?,
                            barcode = ?, gst = ?, hsn = ?, stock = ?, min_stock = ?, updated_at = ?
                        WHERE id = ?
                        ''',
                        (
                            data['product_name'],
                            data['category'],
                            data['price'],
                            data['description'],
                            data['image'],
                            data['purchase_price'],
                            data['selling_price'],
                            data['wholesale_price'],
                            data['barcode'],
                            data['gst'],
                            data['hsn'],
                            data['stock'],
                            data['min_stock'],
                            datetime.now().isoformat(timespec='seconds'),
                            existing['id'],
                        ),
                    )
                    report.updated += 1
                else:
                    data = _normalize_payload(payload)
                    now = datetime.now().isoformat(timespec='seconds')
                    connection.execute(
                        '''
                        INSERT INTO products (
                            product_name, category, price, description, image,
                            purchase_price, selling_price, wholesale_price,
                            barcode, gst, hsn, stock, min_stock,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            data['product_name'],
                            data['category'],
                            data['price'],
                            data['description'],
                            data['image'],
                            data['purchase_price'],
                            data['selling_price'],
                            data['wholesale_price'],
                            data['barcode'],
                            data['gst'],
                            data['hsn'],
                            data['stock'],
                            data['min_stock'],
                            now,
                            now,
                        ),
                    )
                    report.added += 1
            except Exception:
                report.errors += 1
                logger.exception('Import row failed: %s', row)

        connection.commit()
    finally:
        connection.close()

    generate_catalog_json()
    return report


def _product_export_dict(product: Dict) -> Dict:
    return {
        'Product Name': product.get('product_name', ''),
        'Category': product.get('category', ''),
        'Purchase Price': product.get('purchase_price', 0),
        'Selling Price': product.get('selling_price', product.get('price', 0)),
        'Wholesale Price': product.get('wholesale_price', 0),
        'Barcode': product.get('barcode', ''),
        'Description': product.get('description', ''),
        'GST': product.get('gst', 0),
        'HSN': product.get('hsn', ''),
        'Stock': product.get('stock', 0),
        'Minimum Stock': product.get('min_stock', 0),
        'Photo': get_catalog_image_path(product.get('image')),
    }


def export_products_excel(file_path: str):
    products = list_products()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Products'

    headers = list(_product_export_dict({}).keys())
    ws.append(headers)
    for product in products:
        row_dict = _product_export_dict(product)
        ws.append([row_dict[h] for h in headers])

    wb.save(file_path)


def export_products_csv(file_path: str):
    products = list_products()
    headers = list(_product_export_dict({}).keys())
    with open(file_path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for product in products:
            writer.writerow(_product_export_dict(product))


def export_products_json(file_path: str):
    products = list_products()
    payload = [_product_export_dict(product) for product in products]
    with open(file_path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2)
        handle.write('\n')


def get_settings() -> Dict:
    connection = get_connection()
    try:
        row = connection.execute('SELECT * FROM settings ORDER BY id DESC LIMIT 1').fetchone()
        if row:
            return dict(row)
        return {}
    finally:
        connection.close()


def update_settings(payload: Dict) -> Dict:
    current = get_settings()
    merged = {
        'github_repo': payload.get('github_repo', current.get('github_repo', 'PatelStoresOrder')),
        'branch': payload.get('branch', current.get('branch', 'main')),
        'website_url': payload.get('website_url', current.get('website_url', '')),
        'images_folder': payload.get('images_folder', current.get('images_folder', 'images')),
        'backup_folder': payload.get('backup_folder', current.get('backup_folder', 'backup')),
        'commit_message': payload.get('commit_message', current.get('commit_message', 'Update catalog')),
        'website_folder': payload.get('website_folder', current.get('website_folder', '.')),
        'database_path': payload.get('database_path', current.get('database_path', 'patelstores.db')),
        'theme': payload.get('theme', current.get('theme', 'dark')),
    }

    connection = get_connection()
    try:
        row = connection.execute('SELECT id FROM settings ORDER BY id DESC LIMIT 1').fetchone()
        if row:
            connection.execute(
                '''
                UPDATE settings
                SET github_repo = ?, branch = ?, website_url = ?, images_folder = ?, backup_folder = ?,
                    commit_message = ?, website_folder = ?, database_path = ?, theme = ?
                WHERE id = ?
                ''',
                (
                    merged['github_repo'],
                    merged['branch'],
                    merged['website_url'],
                    merged['images_folder'],
                    merged['backup_folder'],
                    merged['commit_message'],
                    merged['website_folder'],
                    merged['database_path'],
                    merged['theme'],
                    row['id'],
                ),
            )
        else:
            connection.execute(
                '''
                INSERT INTO settings (
                    github_repo, branch, website_url, images_folder, backup_folder,
                    commit_message, website_folder, database_path, theme
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    merged['github_repo'],
                    merged['branch'],
                    merged['website_url'],
                    merged['images_folder'],
                    merged['backup_folder'],
                    merged['commit_message'],
                    merged['website_folder'],
                    merged['database_path'],
                    merged['theme'],
                ),
            )
        connection.commit()
    finally:
        connection.close()

    return get_settings()


def create_backup_snapshot() -> Path:
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = BACKUP_DIR / f'publish-backup-{stamp}'
    backup_path.mkdir(parents=True, exist_ok=True)

    db_target = backup_path / DB_PATH.name
    shutil.copy2(DB_PATH, db_target)

    json_path = ROOT_DIR / 'products.json'
    if json_path.exists():
        shutil.copy2(json_path, backup_path / 'products.json')

    images_target = backup_path / 'images'
    if IMAGES_DIR.exists():
        shutil.copytree(IMAGES_DIR, images_target, dirs_exist_ok=True)

    return backup_path


def publish_changes(progress: Callable[[int, str], None]) -> Dict:
    settings = get_settings()
    branch = settings.get('branch') or 'main'
    commit_message = settings.get('commit_message') or 'Update catalog'

    def step(percent: int, message: str):
        logger.info('Publish %s%% - %s', percent, message)
        progress(percent, message)

    step(5, 'Creating backup')
    backup_path = create_backup_snapshot()

    step(20, 'Generating products.json')
    generate_catalog_json()

    step(35, 'Running git add')
    subprocess.run(['git', 'add', '.'], cwd=ROOT_DIR, check=True, capture_output=True, text=True)

    step(60, 'Running git commit')
    commit_proc = subprocess.run(
        ['git', 'commit', '-m', commit_message],
        cwd=ROOT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )

    commit_output = (commit_proc.stdout + '\n' + commit_proc.stderr).lower()
    if commit_proc.returncode != 0 and 'nothing to commit' not in commit_output:
        raise RuntimeError(commit_proc.stderr.strip() or commit_proc.stdout.strip() or 'Git commit failed.')

    step(85, 'Running git push')
    subprocess.run(['git', 'push', 'origin', branch], cwd=ROOT_DIR, check=True, capture_output=True, text=True)

    step(100, 'Publish completed')
    return {
        'success': True,
        'backup_path': str(backup_path),
        'branch': branch,
    }
