from admin.database.db import init_db
from admin.services.catalog import generate_catalog_json


def main():
    init_db()
    products = generate_catalog_json()
    print(f'Wrote {len(products)} products to products.json')


if __name__ == '__main__':
    main()
