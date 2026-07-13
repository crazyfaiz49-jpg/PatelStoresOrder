import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from admin.database.db import init_db
from admin.services.catalog import (
    create_category,
    create_product,
    delete_product,
    get_settings,
    list_categories,
    list_products,
    update_product,
    update_settings,
)

app = Flask(__name__, template_folder='templates', static_folder='static', root_path=str(Path(__file__).resolve().parent))
init_db()


@app.route('/')
def index():
    return render_template('index.html', products=list_products(), categories=list_categories(), settings=get_settings())


@app.route('/api/products')
def api_products():
    return jsonify(list_products(search=request.args.get('search', ''), category=request.args.get('category', '')))


@app.route('/api/categories')
def api_categories():
    return jsonify(list_categories())


@app.route('/api/settings')
def api_settings():
    return jsonify(get_settings())


@app.route('/api/products', methods=['POST'])
def api_create_product():
    payload = request.form.to_dict(flat=True)
    uploaded_file = request.files.get('image') if request.files else None
    image_source = ''
    if uploaded_file and uploaded_file.filename:
        suffix = Path(uploaded_file.filename).suffix or '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            uploaded_file.save(tmp.name)
            image_source = tmp.name
    try:
        create_product(payload, image_source=image_source)
    finally:
        if image_source:
            Path(image_source).unlink(missing_ok=True)
    return jsonify({'success': True})


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def api_update_product(product_id: int):
    payload = request.form.to_dict(flat=True)
    uploaded_file = request.files.get('image') if request.files else None
    image_source = ''
    if uploaded_file and uploaded_file.filename:
        suffix = Path(uploaded_file.filename).suffix or '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            uploaded_file.save(tmp.name)
            image_source = tmp.name
    try:
        update_product(product_id, payload, image_source=image_source)
    finally:
        if image_source:
            Path(image_source).unlink(missing_ok=True)
    return jsonify({'success': True})


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def api_delete_product(product_id: int):
    delete_product(product_id)
    return jsonify({'success': True})


@app.route('/api/categories', methods=['POST'])
def api_create_category():
    payload = request.form.to_dict(flat=True)
    create_category(payload.get('category_name', ''))
    return jsonify({'success': True})


@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    payload = request.form.to_dict(flat=True)
    update_settings(payload)
    return jsonify({'success': True})


@app.route('/publish')
def publish():
    from admin.services.catalog import generate_catalog_json

    generate_catalog_json()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
