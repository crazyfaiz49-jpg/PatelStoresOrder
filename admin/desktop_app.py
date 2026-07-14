from functools import partial
import sys
import traceback
from pathlib import Path

from PySide6 import QtCore, QtGui, QtPrintSupport, QtWidgets

def _resolve_runtime_root() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[1]

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


ROOT = _resolve_runtime_root()
sys.path.insert(0, str(ROOT))

from admin.database.db import init_db
from admin.services.catalog import (
    create_category,
    create_retailer,
    create_product,
    delete_category,
    delete_retailer,
    delete_product,
    duplicate_product,
    export_retailers_excel,
    export_order_pdf,
    export_orders_excel,
    export_products_csv,
    export_products_excel,
    export_products_json,
    generate_product_import_sample,
    get_order,
    get_retailer,
    get_settings,
    import_retailers_from_excel,
    import_products_from_excel,
    list_products_lookup,
    list_orders,
    list_retailers,
    list_categories,
    list_products,
    publish_changes,
    rename_category,
    save_order,
    delete_order,
    print_order,
    update_retailer,
    update_product,
    update_products_status,
    update_settings,
)
from admin.utils.logger import get_logger

logger = get_logger(__name__)


class ImageDropLabel(QtWidgets.QLabel):
    dropped = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumHeight(180)
        self.setWordWrap(True)
        self.setStyleSheet('border: 1px dashed #5e6ad2; border-radius: 12px; padding: 8px;')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            local_path = urls[0].toLocalFile()
            if local_path:
                self.dropped.emit(local_path)
                event.acceptProposedAction()


class ProductDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product
        self.image_source = ''
        self.setWindowTitle('Add Product' if product is None else 'Edit Product')
        self.resize(720, 620)
        self._input_widgets = []
        self._build_ui()
        self._load_categories()
        if product:
            self._fill_form()
        QtCore.QTimer.singleShot(0, self.product_name.setFocus)

    def _register_keyboard_flow(self):
        self._input_widgets = [
            self.product_name,
            self.category,
            self.purchase_price,
            self.selling_price,
            self.wholesale_price,
            self.barcode,
            self.gst,
            self.hsn,
            self.stock,
            self.min_stock,
            self.status,
            self.description,
        ]
        for widget in self._input_widgets:
            widget.installEventFilter(self)

    def _update_margin_label(self):
        cost = float(self.purchase_price.value() or 0)
        sell = float(self.selling_price.value() or 0)
        margin = 0.0 if sell <= 0 else ((sell - cost) / sell) * 100
        self.margin_label.setText(f'Margin: {margin:.2f}%')

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if obj in self._input_widgets:
                self.focusNextChild()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QGridLayout()

        self.product_name = QtWidgets.QLineEdit()
        self.category = QtWidgets.QComboBox()
        self.category.setEditable(True)
        self.add_category_btn = QtWidgets.QPushButton('Add Category')
        self.add_category_btn.clicked.connect(self._add_category_inline)

        self.purchase_price = QtWidgets.QDoubleSpinBox()
        self.purchase_price.setRange(0, 9999999)
        self.purchase_price.setDecimals(2)

        self.selling_price = QtWidgets.QDoubleSpinBox()
        self.selling_price.setRange(0, 9999999)
        self.selling_price.setDecimals(2)

        self.wholesale_price = QtWidgets.QDoubleSpinBox()
        self.wholesale_price.setRange(0, 9999999)
        self.wholesale_price.setDecimals(2)

        self.barcode = QtWidgets.QLineEdit()
        self.gst = QtWidgets.QDoubleSpinBox()
        self.gst.setRange(0, 100)
        self.gst.setDecimals(2)

        self.hsn = QtWidgets.QLineEdit()
        self.stock = QtWidgets.QDoubleSpinBox()
        self.stock.setRange(0, 999999)
        self.stock.setDecimals(2)

        self.min_stock = QtWidgets.QDoubleSpinBox()
        self.min_stock.setRange(0, 999999)
        self.min_stock.setDecimals(2)

        self.status = QtWidgets.QComboBox()
        self.status.addItems(['Active', 'Inactive'])

        self.margin_label = QtWidgets.QLabel('Margin: 0.00%')
        self.margin_label.setStyleSheet('font-weight: 600; color: #0ea5e9;')

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setMaximumHeight(120)

        row = 0
        form.addWidget(QtWidgets.QLabel('Product Name'), row, 0)
        form.addWidget(self.product_name, row, 1)
        form.addWidget(QtWidgets.QLabel('Category'), row, 2)
        category_wrap = QtWidgets.QHBoxLayout()
        category_wrap.addWidget(self.category)
        category_wrap.addWidget(self.add_category_btn)
        category_widget = QtWidgets.QWidget()
        category_widget.setLayout(category_wrap)
        form.addWidget(category_widget, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Purchase Price'), row, 0)
        form.addWidget(self.purchase_price, row, 1)
        form.addWidget(QtWidgets.QLabel('Selling Price'), row, 2)
        form.addWidget(self.selling_price, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Wholesale Price'), row, 0)
        form.addWidget(self.wholesale_price, row, 1)
        form.addWidget(QtWidgets.QLabel('Barcode'), row, 2)
        form.addWidget(self.barcode, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('GST (%)'), row, 0)
        form.addWidget(self.gst, row, 1)
        form.addWidget(QtWidgets.QLabel('HSN'), row, 2)
        form.addWidget(self.hsn, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Stock'), row, 0)
        form.addWidget(self.stock, row, 1)
        form.addWidget(QtWidgets.QLabel('Minimum Stock'), row, 2)
        form.addWidget(self.min_stock, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Description'), row, 0)
        form.addWidget(self.description, row, 1, 1, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Status'), row, 0)
        form.addWidget(self.status, row, 1)
        form.addWidget(self.margin_label, row, 2, 1, 2)

        layout.addLayout(form)

        image_row = QtWidgets.QHBoxLayout()
        self.image_button = QtWidgets.QPushButton('Choose / Replace Photo')
        self.image_button.clicked.connect(self._choose_image)
        image_row.addWidget(self.image_button)
        self.image_info = QtWidgets.QLabel('No image selected')
        self.image_info.setStyleSheet('color: #94a3b8;')
        image_row.addWidget(self.image_info)
        image_row.addStretch()
        layout.addLayout(image_row)

        self.preview = ImageDropLabel()
        self.preview.setText('Drag and drop image here')
        self.preview.dropped.connect(self._set_image)
        layout.addWidget(self.preview)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.purchase_price.valueChanged.connect(self._update_margin_label)
        self.selling_price.valueChanged.connect(self._update_margin_label)
        self._register_keyboard_flow()
        self._update_margin_label()

    def _load_categories(self):
        current = self.category.currentText()
        self.category.clear()
        for item in list_categories():
            self.category.addItem(item['category_name'])
        if current:
            self.category.setCurrentText(current)

    def _add_category_inline(self):
        name = self.category.currentText().strip()
        if not name:
            return
        create_category(name)
        self._load_categories()
        self.category.setCurrentText(name)

    def _fill_form(self):
        self.product_name.setText(self.product.get('product_name', ''))
        self.category.setCurrentText(self.product.get('category', 'General'))
        self.purchase_price.setValue(float(self.product.get('purchase_price', 0) or 0))
        self.selling_price.setValue(float(self.product.get('selling_price', self.product.get('price', 0)) or 0))
        self.wholesale_price.setValue(float(self.product.get('wholesale_price', 0) or 0))
        self.barcode.setText(self.product.get('barcode', ''))
        self.gst.setValue(float(self.product.get('gst', 0) or 0))
        self.hsn.setText(self.product.get('hsn', ''))
        self.stock.setValue(float(self.product.get('stock', 0) or 0))
        self.min_stock.setValue(float(self.product.get('min_stock', 0) or 0))
        self.status.setCurrentText(self.product.get('status', 'Active'))
        self.description.setPlainText(self.product.get('description', ''))
        image_path = self.product.get('image_path', '')
        if image_path:
            self.image_info.setText(image_path)
            self._set_preview(str(ROOT / image_path.replace('/', '\\')))
        self._update_margin_label()

    def _choose_image(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Select Image',
            str(ROOT / 'images'),
            'Images (*.png *.jpg *.jpeg *.webp *.bmp)',
        )
        if file_path:
            self._set_image(file_path)

    def _set_image(self, file_path: str):
        self.image_source = file_path
        self.image_info.setText(Path(file_path).name)
        self._set_preview(file_path)

    def _set_preview(self, file_path: str):
        pixmap = QtGui.QPixmap(file_path)
        if pixmap.isNull():
            self.preview.setText('Preview unavailable')
            self.preview.setPixmap(QtGui.QPixmap())
            return
        scaled = pixmap.scaled(260, 220, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.preview.setPixmap(scaled)

    def _on_save(self):
        if not self.product_name.text().strip():
            QtWidgets.QMessageBox.warning(self, 'Validation', 'Product Name is required.')
            return
        if not self.category.currentText().strip():
            QtWidgets.QMessageBox.warning(self, 'Validation', 'Category is required.')
            return
        self.accept()

    def payload(self):
        return {
            'product_name': self.product_name.text().strip(),
            'category': self.category.currentText().strip(),
            'purchase_price': self.purchase_price.value(),
            'selling_price': self.selling_price.value(),
            'wholesale_price': self.wholesale_price.value(),
            'barcode': self.barcode.text().strip(),
            'description': self.description.toPlainText().strip(),
            'gst': self.gst.value(),
            'hsn': self.hsn.text().strip(),
            'stock': self.stock.value(),
            'min_stock': self.min_stock.value(),
            'status': self.status.currentText(),
            'image': self.product.get('image', '') if self.product else '',
        }


class CategoryDialog(QtWidgets.QDialog):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Manage Categories')
        self.resize(520, 450)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search categories')
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)

        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget)

        button_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton('Add')
        rename_btn = QtWidgets.QPushButton('Rename')
        delete_btn = QtWidgets.QPushButton('Delete')
        add_btn.clicked.connect(self._add)
        rename_btn.clicked.connect(self._rename)
        delete_btn.clicked.connect(self._delete)
        button_row.addWidget(add_btn)
        button_row.addWidget(rename_btn)
        button_row.addWidget(delete_btn)
        layout.addLayout(button_row)

    def _refresh(self):
        self.list_widget.clear()
        for category in list_categories(self.search.text().strip()):
            item = QtWidgets.QListWidgetItem(category['category_name'])
            item.setData(QtCore.Qt.UserRole, category['id'])
            self.list_widget.addItem(item)

    def _add(self):
        name, ok = QtWidgets.QInputDialog.getText(self, 'Add Category', 'Category Name')
        if ok and name.strip():
            create_category(name.strip())
            self._refresh()
            self.changed.emit()

    def _rename(self):
        selected = self.list_widget.currentItem()
        if not selected:
            return
        new_name, ok = QtWidgets.QInputDialog.getText(self, 'Rename Category', 'New Name', text=selected.text())
        if ok and new_name.strip():
            rename_category(selected.data(QtCore.Qt.UserRole), new_name.strip())
            self._refresh()
            self.changed.emit()

    def _delete(self):
        selected = self.list_widget.currentItem()
        if not selected:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            'Delete Category',
            f"Delete category '{selected.text()}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        try:
            delete_category(selected.data(QtCore.Qt.UserRole))
            self._refresh()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Category In Use', str(ex))


class SettingsDialog(QtWidgets.QDialog):
    saved = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Settings')
        self.resize(620, 420)
        self.settings = get_settings()
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)

        self.github_repo = QtWidgets.QLineEdit(self.settings.get('github_repo', ''))
        self.branch = QtWidgets.QLineEdit(self.settings.get('branch', 'main'))
        self.commit_message = QtWidgets.QLineEdit(self.settings.get('commit_message', 'Update catalog'))
        self.images_folder = QtWidgets.QLineEdit(self.settings.get('images_folder', 'images'))
        self.website_folder = QtWidgets.QLineEdit(self.settings.get('website_folder', '.'))
        self.database_path = QtWidgets.QLineEdit(self.settings.get('database_path', 'patelstores.db'))
        self.backup_folder = QtWidgets.QLineEdit(self.settings.get('backup_folder', 'backup'))
        self.website_url = QtWidgets.QLineEdit(self.settings.get('website_url', ''))

        layout.addRow('GitHub Repository', self.github_repo)
        layout.addRow('Branch', self.branch)
        layout.addRow('Commit Message', self.commit_message)
        layout.addRow('Images Folder', self.images_folder)
        layout.addRow('Website Folder', self.website_folder)
        layout.addRow('Database', self.database_path)
        layout.addRow('Backup Folder', self.backup_folder)
        layout.addRow('Website URL', self.website_url)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _save(self):
        updated = update_settings(
            {
                'github_repo': self.github_repo.text().strip(),
                'branch': self.branch.text().strip(),
                'commit_message': self.commit_message.text().strip(),
                'images_folder': self.images_folder.text().strip(),
                'website_folder': self.website_folder.text().strip(),
                'database_path': self.database_path.text().strip(),
                'backup_folder': self.backup_folder.text().strip(),
                'website_url': self.website_url.text().strip(),
            }
        )
        self.saved.emit(updated)
        self.accept()


class OrderDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, order=None):
        super().__init__(parent)
        self.order = order
        self.products = list_products_lookup()
        self.retailers = list_retailers()
        self.setWindowTitle('Create Order' if order is None else 'Edit Order')
        self.resize(980, 720)
        self._build_ui()
        if order:
            self._fill_form()
        elif self.products:
            self._add_item_row()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QGridLayout()

        self.order_number = QtWidgets.QLineEdit()
        self.order_number.setReadOnly(True)
        self.order_number.setPlaceholderText('Auto generated on save')

        self.retailer = QtWidgets.QComboBox()
        self.retailer.setEditable(True)
        self._load_retailers()

        self.order_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.order_date.setCalendarPopup(True)

        self.status = QtWidgets.QComboBox()
        self.status.addItems(['Pending', 'Confirmed', 'Dispatched', 'Delivered'])

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setMaximumHeight(90)

        form.addWidget(QtWidgets.QLabel('Order Number'), 0, 0)
        form.addWidget(self.order_number, 0, 1)
        form.addWidget(QtWidgets.QLabel('Retailer'), 0, 2)
        form.addWidget(self.retailer, 0, 3)
        form.addWidget(QtWidgets.QLabel('Order Date'), 1, 0)
        form.addWidget(self.order_date, 1, 1)
        form.addWidget(QtWidgets.QLabel('Status'), 1, 2)
        form.addWidget(self.status, 1, 3)
        form.addWidget(QtWidgets.QLabel('Notes'), 2, 0)
        form.addWidget(self.notes, 2, 1, 1, 3)
        layout.addLayout(form)

        item_header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('Order Items')
        title.setStyleSheet('font-size: 16px; font-weight: 700;')
        item_header.addWidget(title)
        item_header.addStretch()
        add_row_btn = QtWidgets.QPushButton('Add Product Row')
        add_row_btn.clicked.connect(self._add_item_row)
        item_header.addWidget(add_row_btn)
        layout.addLayout(item_header)

        self.items_table = QtWidgets.QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(['Product', 'Quantity', 'Wholesale Price', 'Line Total', 'Action'])
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.items_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        layout.addWidget(self.items_table)

        self.total_label = QtWidgets.QLabel('Total Amount: 0.00')
        self.total_label.setStyleSheet('font-size: 16px; font-weight: 700;')
        layout.addWidget(self.total_label)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_retailers(self):
        current = self.retailer.currentText()
        self.retailer.blockSignals(True)
        self.retailer.clear()
        for retailer in self.retailers:
            self.retailer.addItem(retailer['shop_name'], retailer['id'])
        if current:
            self.retailer.setCurrentText(current)
        self.retailer.blockSignals(False)

    def _load_products_into_combo(self, combo: QtWidgets.QComboBox):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem('Select Product', 0)
        for product in self.products:
            combo.addItem(product['product_name'], product['id'])
        combo.blockSignals(False)

    def _product_by_id(self, product_id: int):
        for product in self.products:
            if int(product['id']) == int(product_id):
                return product
        return None

    def _add_item_row(self, item=None):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)

        product_combo = QtWidgets.QComboBox()
        self._load_products_into_combo(product_combo)
        quantity_spin = QtWidgets.QDoubleSpinBox()
        quantity_spin.setRange(0, 999999)
        quantity_spin.setDecimals(2)
        quantity_spin.setValue(float(item.get('quantity', 1) if item else 1))
        price_spin = QtWidgets.QDoubleSpinBox()
        price_spin.setRange(0, 9999999)
        price_spin.setDecimals(2)
        price_spin.setValue(float(item.get('wholesale_price', 0) if item else 0))
        price_spin.setProperty('keep_price', bool(item))
        price_spin.editingFinished.connect(lambda spin=price_spin: spin.setProperty('keep_price', True))
        total_item = QtWidgets.QTableWidgetItem('0.00')
        total_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        remove_btn = QtWidgets.QPushButton('Remove')
        remove_btn.clicked.connect(lambda _=False, button=remove_btn: self._remove_button_row(button))

        self.items_table.setCellWidget(row, 0, product_combo)
        self.items_table.setCellWidget(row, 1, quantity_spin)
        self.items_table.setCellWidget(row, 2, price_spin)
        self.items_table.setItem(row, 3, total_item)
        self.items_table.setCellWidget(row, 4, remove_btn)

        product_combo.currentIndexChanged.connect(self._sync_item_rows)
        quantity_spin.valueChanged.connect(self._sync_item_rows)
        price_spin.valueChanged.connect(self._sync_item_rows)

        if item:
            product_combo.setCurrentIndex(max(0, product_combo.findData(int(item.get('product_id', 0)))))
        else:
            self._apply_product_defaults(row)

        self._sync_item_rows()

    def _remove_button_row(self, button):
        index = self.items_table.indexAt(button.mapTo(self.items_table.viewport(), button.rect().center()))
        row = index.row()
        if row < 0:
            return
        self.items_table.removeRow(row)
        self._sync_item_rows()
        if self.items_table.rowCount() == 0:
            self._add_item_row()

    def _apply_product_defaults(self, row: int):
        combo = self.items_table.cellWidget(row, 0)
        price_spin = self.items_table.cellWidget(row, 2)
        if not combo or not price_spin:
            return
        product = self._product_by_id(combo.currentData() or 0)
        if product:
            price_spin.blockSignals(True)
            price_spin.setValue(float(product.get('default_wholesale_price', 0) or 0))
            price_spin.blockSignals(False)

    def _sync_item_rows(self):
        total_amount = 0.0
        for row in range(self.items_table.rowCount()):
            combo = self.items_table.cellWidget(row, 0)
            quantity_spin = self.items_table.cellWidget(row, 1)
            price_spin = self.items_table.cellWidget(row, 2)
            total_item = self.items_table.item(row, 3)
            if not combo or not quantity_spin or not price_spin or not total_item:
                continue
            product = self._product_by_id(combo.currentData() or 0)
            if product and not price_spin.property('keep_price'):
                price_spin.blockSignals(True)
                price_spin.setValue(float(product.get('default_wholesale_price', 0) or 0))
                price_spin.blockSignals(False)
            row_total = round(float(quantity_spin.value()) * float(price_spin.value()), 2)
            total_item.setText(f'{row_total:.2f}')
            total_amount += row_total
        self.total_label.setText(f'Total Amount: {total_amount:.2f}')

    def _fill_form(self):
        self.order_number.setText(self.order.get('order_number', ''))
        self.retailer.setCurrentText(self.order.get('retailer_name', ''))
        if self.order.get('order_date'):
            self.order_date.setDate(QtCore.QDate.fromString(self.order['order_date'], 'yyyy-MM-dd'))
        self.status.setCurrentText(self.order.get('status', 'Pending'))
        self.notes.setPlainText(self.order.get('notes', ''))
        self.items_table.setRowCount(0)
        for item in self.order.get('items', []):
            self._add_item_row(item)

    def payload(self):
        retailer_id = self.retailer.currentData()
        if retailer_id is None:
            retailer_name = self.retailer.currentText().strip()
            retailer_id = 0
            for retailer in self.retailers:
                if retailer['shop_name'].lower() == retailer_name.lower():
                    retailer_id = retailer['id']
                    break
        items = []
        for row in range(self.items_table.rowCount()):
            combo = self.items_table.cellWidget(row, 0)
            quantity_spin = self.items_table.cellWidget(row, 1)
            price_spin = self.items_table.cellWidget(row, 2)
            if not combo or not quantity_spin or not price_spin:
                continue
            product_id = combo.currentData() or 0
            if int(product_id) <= 0:
                continue
            product = self._product_by_id(product_id)
            items.append({
                'product_id': int(product_id),
                'product_name': product['product_name'] if product else combo.currentText(),
                'quantity': quantity_spin.value(),
                'wholesale_price': price_spin.value(),
            })
        return {
            'retailer_id': int(retailer_id or 0),
            'order_date': self.order_date.date().toString('yyyy-MM-dd'),
            'status': self.status.currentText(),
            'notes': self.notes.toPlainText().strip(),
            'items': items,
        }

    def _on_save(self):
        data = self.payload()
        if data['retailer_id'] <= 0:
            QtWidgets.QMessageBox.warning(self, 'Validation', 'Retailer is required.')
            return
        if not data['items']:
            QtWidgets.QMessageBox.warning(self, 'Validation', 'Add at least one product row.')
            return
        self.accept()


class OrderManagementDialog(QtWidgets.QDialog):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Order Management')
        self.resize(1420, 800)
        self.orders = []
        self._build_ui()
        self.refresh_orders()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('Order Management')
        title.setStyleSheet('font-size: 20px; font-weight: 700;')
        header.addWidget(title)
        header.addStretch()
        add_btn = QtWidgets.QPushButton('Create Order')
        edit_btn = QtWidgets.QPushButton('Edit Order')
        delete_btn = QtWidgets.QPushButton('Delete Order')
        print_btn = QtWidgets.QPushButton('Print Order')
        export_excel_btn = QtWidgets.QPushButton('Export Excel')
        export_pdf_btn = QtWidgets.QPushButton('Export PDF')
        refresh_btn = QtWidgets.QPushButton('Refresh')
        add_btn.clicked.connect(self.add_order)
        edit_btn.clicked.connect(self.edit_selected_order)
        delete_btn.clicked.connect(self.delete_selected_order)
        print_btn.clicked.connect(self.print_selected_order)
        export_excel_btn.clicked.connect(self.export_excel)
        export_pdf_btn.clicked.connect(self.export_pdf)
        refresh_btn.clicked.connect(self.refresh_orders)
        for button in [add_btn, edit_btn, delete_btn, print_btn, export_excel_btn, export_pdf_btn, refresh_btn]:
            header.addWidget(button)
        layout.addLayout(header)

        filters = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search orders by order number, retailer, owner, notes')
        self.search.textChanged.connect(self.refresh_orders)

        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(['All', 'Pending', 'Confirmed', 'Dispatched', 'Delivered'])
        self.status_filter.currentIndexChanged.connect(self.refresh_orders)

        self.retailer_filter = QtWidgets.QComboBox()
        self.retailer_filter.setEditable(True)
        self.retailer_filter.currentIndexChanged.connect(self.refresh_orders)

        filters.addWidget(self.search, 4)
        filters.addWidget(self.status_filter, 1)
        filters.addWidget(self.retailer_filter, 2)
        layout.addLayout(filters)

        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Order Number', 'Order Date', 'Retailer', 'Status', 'Total Amount', 'Notes', 'ID'])
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_order())
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)
        self.table.setColumnHidden(6, True)

        self.status_label = QtWidgets.QLabel('Ready')
        layout.addWidget(self.status_label)

    def _load_retailers(self):
        current = self.retailer_filter.currentText()
        self.retailer_filter.blockSignals(True)
        self.retailer_filter.clear()
        self.retailer_filter.addItem('All')
        for retailer in list_retailers():
            self.retailer_filter.addItem(retailer['shop_name'])
        if current:
            index = self.retailer_filter.findText(current)
            if index >= 0:
                self.retailer_filter.setCurrentIndex(index)
            else:
                self.retailer_filter.setCurrentText(current)
        self.retailer_filter.blockSignals(False)

    def refresh_orders(self):
        self._load_retailers()
        status = self.status_filter.currentText()
        retailer = self.retailer_filter.currentText().strip()
        if retailer == 'All':
            retailer = ''
        self.orders = list_orders(
            search=self.search.text().strip(),
            status=status,
            retailer=retailer,
        )

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for order in self.orders:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                order.get('order_number', ''),
                order.get('order_date', ''),
                order.get('retailer_name', ''),
                order.get('status', ''),
                f"{float(order.get('total_amount', 0) or 0):.2f}",
                order.get('notes', ''),
                str(order.get('id', '')),
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col == 4:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.status_label.setText(f'{len(self.orders)} orders loaded')

    def _selected_order_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 6)
        if not item:
            return None
        return int(item.text())

    def _selected_order(self):
        order_id = self._selected_order_id()
        if order_id is None:
            return None
        return get_order(order_id)

    def add_order(self):
        dialog = OrderDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            data = dialog.payload()
            save_order(data, data['items'])
            self.refresh_orders()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Create Order', str(ex))

    def edit_selected_order(self):
        selected = self._selected_order()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Edit Order', 'Select an order to edit.')
            return
        dialog = OrderDialog(self, selected)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            data = dialog.payload()
            save_order(data, data['items'], order_id=selected['id'])
            self.refresh_orders()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Edit Order', str(ex))

    def delete_selected_order(self):
        selected = self._selected_order()
        if not selected:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            'Delete Order',
            f"Delete order '{selected['order_number']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        try:
            delete_order(selected['id'])
            self.refresh_orders()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Delete Order', str(ex))

    def print_selected_order(self):
        selected = self._selected_order()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Print Order', 'Select an order to print.')
            return
        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        dialog = QtPrintSupport.QPrintDialog(printer, self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            print_order(selected['id'], printer)
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Print Order', str(ex))

    def export_excel(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Export Orders to Excel',
            str(ROOT / 'orders_export.xlsx'),
            'Excel (*.xlsx)',
        )
        if file_path:
            try:
                export_orders_excel(file_path)
            except Exception as ex:
                QtWidgets.QMessageBox.warning(self, 'Export Excel', str(ex))

    def export_pdf(self):
        selected = self._selected_order()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Export PDF', 'Select an order to export.')
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Export Order PDF',
            str(ROOT / f"{selected['order_number']}.pdf"),
            'PDF (*.pdf)',
        )
        if file_path:
            try:
                export_order_pdf(selected['id'], file_path)
            except Exception as ex:
                QtWidgets.QMessageBox.warning(self, 'Export PDF', str(ex))

    def show_context_menu(self, point):
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction('Edit')
        delete_action = menu.addAction('Delete')
        print_action = menu.addAction('Print')
        action = menu.exec(self.table.mapToGlobal(point))
        if action == edit_action:
            self.edit_selected_order()
        elif action == delete_action:
            self.delete_selected_order()
        elif action == print_action:
            self.print_selected_order()


class RetailerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, retailer=None):
        super().__init__(parent)
        self.retailer = retailer
        self.setWindowTitle('Add Retailer' if retailer is None else 'Edit Retailer')
        self.resize(780, 560)
        self._build_ui()
        if retailer:
            self._fill_form()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QGridLayout()

        self.shop_name = QtWidgets.QLineEdit()
        self.owner_name = QtWidgets.QLineEdit()
        self.mobile_number = QtWidgets.QLineEdit()
        self.whatsapp_number = QtWidgets.QLineEdit()
        self.address = QtWidgets.QPlainTextEdit()
        self.address.setMaximumHeight(110)
        self.city = QtWidgets.QLineEdit()
        self.gst_number = QtWidgets.QLineEdit()
        self.credit_limit = QtWidgets.QDoubleSpinBox()
        self.credit_limit.setRange(0, 99999999)
        self.credit_limit.setDecimals(2)
        self.outstanding_balance = QtWidgets.QDoubleSpinBox()
        self.outstanding_balance.setRange(0, 99999999)
        self.outstanding_balance.setDecimals(2)
        self.status = QtWidgets.QComboBox()
        self.status.addItems(['Active', 'Inactive'])

        row = 0
        form.addWidget(QtWidgets.QLabel('Shop Name'), row, 0)
        form.addWidget(self.shop_name, row, 1)
        form.addWidget(QtWidgets.QLabel('Owner Name'), row, 2)
        form.addWidget(self.owner_name, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Mobile Number'), row, 0)
        form.addWidget(self.mobile_number, row, 1)
        form.addWidget(QtWidgets.QLabel('WhatsApp Number'), row, 2)
        form.addWidget(self.whatsapp_number, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('City'), row, 0)
        form.addWidget(self.city, row, 1)
        form.addWidget(QtWidgets.QLabel('GST Number'), row, 2)
        form.addWidget(self.gst_number, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Credit Limit'), row, 0)
        form.addWidget(self.credit_limit, row, 1)
        form.addWidget(QtWidgets.QLabel('Outstanding Balance'), row, 2)
        form.addWidget(self.outstanding_balance, row, 3)

        row += 1
        form.addWidget(QtWidgets.QLabel('Status'), row, 0)
        form.addWidget(self.status, row, 1)

        row += 1
        form.addWidget(QtWidgets.QLabel('Address'), row, 0)
        form.addWidget(self.address, row, 1, 1, 3)

        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill_form(self):
        self.shop_name.setText(self.retailer.get('shop_name', ''))
        self.owner_name.setText(self.retailer.get('owner_name', ''))
        self.mobile_number.setText(self.retailer.get('mobile_number', ''))
        self.whatsapp_number.setText(self.retailer.get('whatsapp_number', ''))
        self.address.setPlainText(self.retailer.get('address', ''))
        self.city.setText(self.retailer.get('city', ''))
        self.gst_number.setText(self.retailer.get('gst_number', ''))
        self.credit_limit.setValue(float(self.retailer.get('credit_limit', 0) or 0))
        self.outstanding_balance.setValue(float(self.retailer.get('outstanding_balance', 0) or 0))
        self.status.setCurrentText(self.retailer.get('status', 'Active'))

    def _on_save(self):
        if not self.shop_name.text().strip():
            QtWidgets.QMessageBox.warning(self, 'Validation', 'Shop Name is required.')
            return
        self.accept()

    def payload(self):
        return {
            'shop_name': self.shop_name.text().strip(),
            'owner_name': self.owner_name.text().strip(),
            'mobile_number': self.mobile_number.text().strip(),
            'whatsapp_number': self.whatsapp_number.text().strip(),
            'address': self.address.toPlainText().strip(),
            'city': self.city.text().strip(),
            'gst_number': self.gst_number.text().strip(),
            'credit_limit': self.credit_limit.value(),
            'outstanding_balance': self.outstanding_balance.value(),
            'status': self.status.currentText(),
        }


class RetailerMasterDialog(QtWidgets.QDialog):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Retailer Master')
        self.resize(1380, 760)
        self.retailers = []
        self._build_ui()
        self.refresh_retailers()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('Retailer Master')
        title.setStyleSheet('font-size: 20px; font-weight: 700;')
        header.addWidget(title)
        header.addStretch()

        add_btn = QtWidgets.QPushButton('Add Retailer')
        edit_btn = QtWidgets.QPushButton('Edit Retailer')
        delete_btn = QtWidgets.QPushButton('Delete Retailer')
        refresh_btn = QtWidgets.QPushButton('Refresh')
        import_btn = QtWidgets.QPushButton('Import Excel')
        export_btn = QtWidgets.QPushButton('Export Excel')
        add_btn.clicked.connect(self.add_retailer)
        edit_btn.clicked.connect(self.edit_selected_retailer)
        delete_btn.clicked.connect(self.delete_selected_retailer)
        refresh_btn.clicked.connect(self.refresh_retailers)
        import_btn.clicked.connect(self.import_excel)
        export_btn.clicked.connect(self.export_excel)
        for button in [add_btn, edit_btn, delete_btn, refresh_btn, import_btn, export_btn]:
            header.addWidget(button)
        layout.addLayout(header)

        filters = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search by shop, owner, mobile, WhatsApp, city, GST, address')
        self.search.textChanged.connect(self.refresh_retailers)

        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(['All', 'Active', 'Inactive'])
        self.status_filter.currentIndexChanged.connect(self.refresh_retailers)

        self.city_filter = QtWidgets.QComboBox()
        self.city_filter.setEditable(True)
        self.city_filter.currentIndexChanged.connect(self.refresh_retailers)

        filters.addWidget(self.search, 4)
        filters.addWidget(self.status_filter, 1)
        filters.addWidget(self.city_filter, 1)
        layout.addLayout(filters)

        self.table = QtWidgets.QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            'Shop Name',
            'Owner Name',
            'Mobile Number',
            'WhatsApp Number',
            'City',
            'GST Number',
            'Credit Limit',
            'Outstanding Balance',
            'Status',
            'Address',
            'ID',
        ])
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_retailer())
        layout.addWidget(self.table)
        self.table.setColumnHidden(10, True)

        self.status_label = QtWidgets.QLabel('Ready')
        layout.addWidget(self.status_label)

    def _populate_city_filter(self):
        current = self.city_filter.currentText()
        self.city_filter.blockSignals(True)
        self.city_filter.clear()
        self.city_filter.addItem('All')
        seen = set()
        for retailer in list_retailers():
            city = (retailer.get('city') or '').strip()
            if city and city.lower() not in seen:
                seen.add(city.lower())
                self.city_filter.addItem(city)
        if current:
            index = self.city_filter.findText(current)
            if index >= 0:
                self.city_filter.setCurrentIndex(index)
            else:
                self.city_filter.setCurrentText(current)
        self.city_filter.blockSignals(False)

    def refresh_retailers(self):
        self._populate_city_filter()
        status = self.status_filter.currentText()
        city = self.city_filter.currentText().strip()
        if city == 'All':
            city = ''
        self.retailers = list_retailers(
            search=self.search.text().strip(),
            status=status,
            city=city,
        )

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for retailer in self.retailers:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                retailer.get('shop_name', ''),
                retailer.get('owner_name', ''),
                retailer.get('mobile_number', ''),
                retailer.get('whatsapp_number', ''),
                retailer.get('city', ''),
                retailer.get('gst_number', ''),
                f"{float(retailer.get('credit_limit', 0) or 0):.2f}",
                f"{float(retailer.get('outstanding_balance', 0) or 0):.2f}",
                retailer.get('status', 'Active'),
                retailer.get('address', ''),
                str(retailer.get('id', '')),
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col in {6, 7}:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, col, item)

            status_value = (retailer.get('status') or 'Active').lower()
            is_dark = self.palette().color(QtGui.QPalette.Window).lightness() < 128
            if status_value == 'active':
                color = QtGui.QColor(24, 66, 44) if is_dark else QtGui.QColor(220, 252, 231)
            else:
                color = QtGui.QColor(88, 28, 28) if is_dark else QtGui.QColor(254, 226, 226)
            for col in range(11):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(color)

        self.table.setSortingEnabled(True)
        self.status_label.setText(f'{len(self.retailers)} retailers loaded')

    def _selected_retailer_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 10)
        if not item:
            return None
        return int(item.text())

    def _selected_retailer(self):
        retailer_id = self._selected_retailer_id()
        if retailer_id is None:
            return None
        for retailer in self.retailers:
            if int(retailer['id']) == int(retailer_id):
                return retailer
        return None

    def add_retailer(self):
        dialog = RetailerDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            create_retailer(dialog.payload())
            self.refresh_retailers()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Add Retailer', str(ex))

    def edit_selected_retailer(self):
        selected = self._selected_retailer()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Edit Retailer', 'Select a retailer to edit.')
            return
        dialog = RetailerDialog(self, selected)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            update_retailer(selected['id'], dialog.payload())
            self.refresh_retailers()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Edit Retailer', str(ex))

    def delete_selected_retailer(self):
        selected = self._selected_retailer()
        if not selected:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            'Delete Retailer',
            f"Delete retailer '{selected['shop_name']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        try:
            delete_retailer(selected['id'])
            self.refresh_retailers()
            self.changed.emit()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Delete Retailer', str(ex))

    def show_context_menu(self, point):
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction('Edit')
        delete_action = menu.addAction('Delete')
        action = menu.exec(self.table.mapToGlobal(point))
        if action == edit_action:
            self.edit_selected_retailer()
        elif action == delete_action:
            self.delete_selected_retailer()

    def import_excel(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Import Retailers From Excel',
            str(ROOT),
            'Excel Files (*.xlsx *.xlsm)',
        )
        if not file_path:
            return
        try:
            report = import_retailers_from_excel(file_path)
            self.refresh_retailers()
            self.changed.emit()
            QtWidgets.QMessageBox.information(
                self,
                'Import Completed',
                f'Added: {report.added}\nUpdated: {report.updated}\nSkipped: {report.skipped}\nErrors: {report.errors}',
            )
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Import Retailers', str(ex))

    def export_excel(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Export Retailers to Excel',
            str(ROOT / 'retailers_export.xlsx'),
            'Excel (*.xlsx)',
        )
        if file_path:
            try:
                export_retailers_excel(file_path)
            except Exception as ex:
                QtWidgets.QMessageBox.warning(self, 'Export Retailers', str(ex))


class AdminWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.settings = get_settings()
        self.products = []
        self.current_theme = self.settings.get('theme', 'dark')
        self._restoring_layout = False
        self._frozen_columns = {1, 2}
        self._build_ui()
        self._build_shortcuts()
        self._apply_theme(self.current_theme)
        self.refresh_products()

    def _build_ui(self):
        self.setWindowTitle('Patel Stores Admin Panel - Mini ERP')
        self.resize(1500, 860)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)

        top = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('Patel Stores Admin Panel')
        title.setStyleSheet('font-size: 22px; font-weight: 700;')
        top.addWidget(title)
        top.addStretch()

        self.theme_btn = QtWidgets.QPushButton('Toggle Theme')
        self.theme_btn.clicked.connect(self.toggle_theme)
        top.addWidget(self.theme_btn)

        self.settings_btn = QtWidgets.QPushButton('Settings')
        self.settings_btn.clicked.connect(self.open_settings)
        top.addWidget(self.settings_btn)

        self.publish_btn = QtWidgets.QPushButton('Publish')
        self.publish_btn.clicked.connect(self.publish)
        top.addWidget(self.publish_btn)

        root.addLayout(top)

        actions = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton('Add Product')
        self.edit_btn = QtWidgets.QPushButton('Edit Product')
        self.dup_btn = QtWidgets.QPushButton('Duplicate Product')
        self.del_btn = QtWidgets.QPushButton('Delete Product')
        self.refresh_btn = QtWidgets.QPushButton('Refresh')
        self.import_btn = QtWidgets.QPushButton('Import Excel')
        self.export_btn = QtWidgets.QPushButton('Export')
        self.categories_btn = QtWidgets.QPushButton('Categories')
        self.retailers_btn = QtWidgets.QPushButton('Retailers')
        self.orders_btn = QtWidgets.QPushButton('Orders')

        self.add_btn.clicked.connect(self.add_product)
        self.edit_btn.clicked.connect(self.edit_selected_product)
        self.dup_btn.clicked.connect(self.duplicate_selected_product)
        self.del_btn.clicked.connect(self.delete_selected_product)
        self.refresh_btn.clicked.connect(self.refresh_products)
        self.import_btn.clicked.connect(self.import_excel)
        self.export_btn.clicked.connect(self.export_products)
        self.categories_btn.clicked.connect(self.manage_categories)
        self.retailers_btn.clicked.connect(self.manage_retailers)
        self.orders_btn.clicked.connect(self.manage_orders)

        for btn in [self.add_btn, self.edit_btn, self.dup_btn, self.del_btn, self.refresh_btn, self.import_btn, self.export_btn, self.categories_btn, self.retailers_btn, self.orders_btn]:
            actions.addWidget(btn)

        actions.addStretch()
        root.addLayout(actions)

        filters = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search by Product Name, Barcode, Category, Price')
        self.search.textChanged.connect(self.refresh_products)

        self.category_filter = QtWidgets.QComboBox()
        self.category_filter.currentIndexChanged.connect(self.refresh_products)

        self.min_price_filter = QtWidgets.QDoubleSpinBox()
        self.min_price_filter.setPrefix('Min Price ')
        self.min_price_filter.setRange(0, 9999999)
        self.min_price_filter.setDecimals(2)
        self.min_price_filter.valueChanged.connect(self.refresh_products)

        self.max_price_filter = QtWidgets.QDoubleSpinBox()
        self.max_price_filter.setPrefix('Max Price ')
        self.max_price_filter.setRange(0, 9999999)
        self.max_price_filter.setDecimals(2)
        self.max_price_filter.setValue(0)
        self.max_price_filter.valueChanged.connect(self.refresh_products)

        self.stock_filter = QtWidgets.QComboBox()
        self.stock_filter.addItems(['All Stock', 'In Stock', 'Out of Stock', 'Low Stock'])
        self.stock_filter.currentIndexChanged.connect(self.refresh_products)

        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(['All Status', 'Active', 'Inactive'])
        self.status_filter.currentIndexChanged.connect(self.refresh_products)

        filters.addWidget(self.search, 3)
        filters.addWidget(self.category_filter, 1)
        filters.addWidget(self.min_price_filter, 1)
        filters.addWidget(self.max_price_filter, 1)
        filters.addWidget(self.stock_filter, 1)
        filters.addWidget(self.status_filter, 1)
        root.addLayout(filters)

        self.table = QtWidgets.QTableWidget(0, 16)
        self.table.setHorizontalHeaderLabels(
            [
                'Sel',
                'Photo',
                'Product Name',
                'Category',
                'Status',
                'Purchase Price',
                'Selling Price',
                'Margin %',
                'Wholesale Price',
                'Barcode',
                'GST',
                'HSN',
                'Stock',
                'Min Stock',
                'Description',
                'ID',
            ]
        )
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.horizontalHeader().sectionMoved.connect(self._on_header_section_moved)
        self.table.horizontalHeader().sectionResized.connect(self._persist_table_layout)
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_product())
        self.table.itemChanged.connect(self._on_row_check_changed)
        root.addWidget(self.table)
        self.table.setColumnHidden(15, True)

        self._restore_table_layout()

        self.status_label = QtWidgets.QLabel('Ready')
        root.addWidget(self.status_label)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

    def _build_shortcuts(self):
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+N'), self, self.add_product)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+E'), self, self.edit_selected_product)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+D'), self, self.duplicate_selected_product)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+I'), self, self.import_excel)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Shift+I'), self, self.download_import_sample)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+S'), self, self.publish)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+R'), self, self.refresh_products)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+F'), self, self.focus_search)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+A'), self, self.table.selectAll)
        QtGui.QShortcut(QtGui.QKeySequence('Space'), self, self.toggle_selected_product_status)
        QtGui.QShortcut(QtGui.QKeySequence('Delete'), self, self.delete_selected_product)
        QtGui.QShortcut(QtGui.QKeySequence('F5'), self, self.refresh_products)

    def _settings_store(self):
        return QtCore.QSettings('PatelStores', 'AdminPanel')

    def _persist_table_layout(self):
        if self._restoring_layout:
            return
        header = self.table.horizontalHeader()
        store = self._settings_store()
        widths = [self.table.columnWidth(i) for i in range(self.table.columnCount())]
        visual = [header.visualIndex(i) for i in range(self.table.columnCount())]
        store.setValue('products.table.widths', widths)
        store.setValue('products.table.visualOrder', visual)

    def _restore_table_layout(self):
        store = self._settings_store()
        widths = store.value('products.table.widths', [])
        visual = store.value('products.table.visualOrder', [])

        self._restoring_layout = True
        try:
            if isinstance(widths, list) and len(widths) == self.table.columnCount():
                for idx, value in enumerate(widths):
                    try:
                        self.table.setColumnWidth(idx, int(value))
                    except Exception:
                        pass
            if isinstance(visual, list) and len(visual) == self.table.columnCount():
                header = self.table.horizontalHeader()
                for logical, visual_idx in enumerate(visual):
                    try:
                        header.moveSection(header.visualIndex(logical), int(visual_idx))
                    except Exception:
                        pass
        finally:
            self._restoring_layout = False

    def _on_header_section_moved(self, logical_index, old_visual_index, new_visual_index):
        if self._restoring_layout:
            return
        header = self.table.horizontalHeader()
        if logical_index in self._frozen_columns:
            self._restoring_layout = True
            try:
                target = 1 if logical_index == 1 else 2
                header.moveSection(header.visualIndex(logical_index), target)
            finally:
                self._restoring_layout = False
            return
        if new_visual_index < 3:
            self._restoring_layout = True
            try:
                header.moveSection(header.visualIndex(logical_index), old_visual_index)
            finally:
                self._restoring_layout = False
            return
        self._persist_table_layout()

    def _on_row_check_changed(self, item):
        if item.column() != 0:
            return
        checked = item.checkState() == QtCore.Qt.Checked
        row = item.row()
        model = self.table.selectionModel()
        if checked:
            model.select(self.table.model().index(row, 0), QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
        else:
            model.select(self.table.model().index(row, 0), QtCore.QItemSelectionModel.Deselect | QtCore.QItemSelectionModel.Rows)

    def _apply_theme(self, theme: str):
        if theme == 'light':
            self.setStyleSheet('''
                QWidget { background: #f8fafc; color: #0f172a; }
                QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QTableWidget {
                    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px;
                }
                QTableWidget {
                    alternate-background-color: #f1f5f9;
                    selection-background-color: #bfdbfe;
                    selection-color: #0f172a;
                    gridline-color: #e2e8f0;
                }
                QPushButton { background: #2563eb; color: #ffffff; border-radius: 10px; padding: 8px 12px; }
                QPushButton:hover { background: #1d4ed8; }
            ''')
        else:
            self.setStyleSheet('''
                QWidget { background: #0f172a; color: #e2e8f0; }
                QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QTableWidget {
                    background: #111827; border: 1px solid #334155; border-radius: 8px; padding: 4px;
                }
                QTableWidget {
                    alternate-background-color: #1f2937;
                    selection-background-color: #1e3a8a;
                    selection-color: #e2e8f0;
                    gridline-color: #334155;
                }
                QPushButton { background: #334155; color: #e2e8f0; border-radius: 10px; padding: 8px 12px; }
                QPushButton:hover { background: #475569; }
            ''')

    def toggle_theme(self):
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self._apply_theme(self.current_theme)
        self.settings = update_settings({'theme': self.current_theme})

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _selected_product_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        id_item = self.table.item(row, 15)
        if not id_item:
            return None
        return int(id_item.text())

    def _selected_product_ids(self):
        rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        ids = []
        for row in rows:
            item = self.table.item(row, 15)
            if item and item.text().strip():
                ids.append(int(item.text()))
        return ids

    def _populate_category_filter(self):
        current = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem('All')
        for item in list_categories():
            self.category_filter.addItem(item['category_name'])
        if current:
            index = self.category_filter.findText(current)
            if index >= 0:
                self.category_filter.setCurrentIndex(index)
        self.category_filter.blockSignals(False)

    def refresh_products(self):
        self._populate_category_filter()
        stock_mode_map = {
            'All Stock': 'all',
            'In Stock': 'in',
            'Out of Stock': 'out',
            'Low Stock': 'low',
        }
        stock_mode = stock_mode_map.get(self.stock_filter.currentText(), 'all')

        category = self.category_filter.currentText()
        if category == 'All':
            category = ''

        self.products = list_products(
            search=self.search.text().strip(),
            category=category,
            min_price=self.min_price_filter.value() if self.min_price_filter.value() > 0 else None,
            max_price=self.max_price_filter.value() if self.max_price_filter.value() > 0 else None,
            stock_mode=stock_mode,
            status=self.status_filter.currentText().replace(' Status', '').lower(),
        )

        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for product in self.products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 66)

            selector = QtWidgets.QTableWidgetItem('')
            selector.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
            selector.setCheckState(QtCore.Qt.Unchecked)
            selector.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 0, selector)

            image_widget = QtWidgets.QLabel()
            image_widget.setAlignment(QtCore.Qt.AlignCenter)
            image_widget.setFixedSize(60, 60)
            pix = QtGui.QPixmap(str(ROOT / product.get('image_path', '').replace('/', '\\')))
            if not pix.isNull():
                image_widget.setPixmap(pix.scaled(56, 56, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                image_widget.setText('N/A')
            self.table.setCellWidget(row, 1, image_widget)

            selling_price = float(product.get('selling_price', product.get('price', 0)) or 0)
            purchase_price = float(product.get('purchase_price', 0) or 0)
            margin = 0.0 if selling_price <= 0 else ((selling_price - purchase_price) / selling_price) * 100

            values = [
                product.get('product_name', ''),
                product.get('category', ''),
                product.get('status', 'Active') or 'Active',
                f"{purchase_price:.2f}",
                f"{selling_price:.2f}",
                f"{margin:.2f}",
                f"{float(product.get('wholesale_price', 0) or 0):.2f}",
                product.get('barcode', ''),
                f"{float(product.get('gst', 0) or 0):.2f}",
                product.get('hsn', ''),
                f"{float(product.get('stock', 0) or 0):.2f}",
                f"{float(product.get('min_stock', 0) or 0):.2f}",
                product.get('description', ''),
                str(product.get('id', '')),
            ]
            for col, value in enumerate(values, start=2):
                item = QtWidgets.QTableWidgetItem(value)
                if col in {5, 6, 7, 8, 10, 12, 13}:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if col == 4:
                    status_value = (value or 'Active').lower()
                    if status_value == 'active':
                        item.setForeground(QtGui.QColor('#15803d'))
                    else:
                        item.setForeground(QtGui.QColor('#b91c1c'))
                self.table.setItem(row, col, item)

            stock = float(product.get('stock', 0) or 0)
            min_stock = float(product.get('min_stock', 0) or 0)
            is_dark = self.palette().color(QtGui.QPalette.Window).lightness() < 128
            if stock <= 0:
                color = QtGui.QColor(127, 29, 29) if is_dark else QtGui.QColor(254, 226, 226)
            elif stock <= min_stock:
                color = QtGui.QColor(120, 53, 15) if is_dark else QtGui.QColor(254, 243, 199)
            else:
                color = QtGui.QColor(15, 23, 42) if is_dark else QtGui.QColor(219, 234, 254)
            for col in range(2, 16):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(color)

        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, max(200, self.table.columnWidth(2)))
        self.table.setColumnWidth(14, max(260, self.table.columnWidth(14)))
        self.table.setSortingEnabled(True)
        self._persist_table_layout()
        self.status_label.setText(f'{len(self.products)} products loaded')

    def _selected_product(self):
        product_id = self._selected_product_id()
        if product_id is None:
            return None
        for product in self.products:
            if int(product['id']) == int(product_id):
                return product
        return None

    def add_product(self):
        dialog = ProductDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            create_product(dialog.payload(), dialog.image_source)
            self.refresh_products()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Add Product', str(ex))

    def edit_selected_product(self):
        selected = self._selected_product()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Edit Product', 'Select a product to edit.')
            return
        dialog = ProductDialog(self, selected)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            update_product(selected['id'], dialog.payload(), dialog.image_source)
            self.refresh_products()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Edit Product', str(ex))

    def duplicate_selected_product(self):
        selected = self._selected_product()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Duplicate Product', 'Select a product to duplicate.')
            return
        try:
            duplicate_product(selected['id'])
            self.refresh_products()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Duplicate Product', str(ex))

    def delete_selected_product(self):
        selected = self._selected_product()
        if not selected:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            'Delete Product',
            f"Delete '{selected['product_name']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        try:
            delete_product(selected['id'])
            self.refresh_products()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Delete Product', str(ex))

    def manage_categories(self):
        dialog = CategoryDialog(self)
        dialog.changed.connect(self.refresh_products)
        dialog.exec()

    def manage_retailers(self):
        dialog = RetailerMasterDialog(self)
        dialog.exec()

    def manage_orders(self):
        dialog = OrderManagementDialog(self)
        dialog.exec()

    def show_context_menu(self, point):
        row = self.table.rowAt(point.y())
        if row >= 0 and not self.table.selectionModel().isRowSelected(row, QtCore.QModelIndex()):
            self.table.selectRow(row)

        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction('Edit')
        duplicate_action = menu.addAction('Duplicate')
        delete_action = menu.addAction('Delete')
        menu.addSeparator()
        activate_action = menu.addAction('Activate')
        deactivate_action = menu.addAction('Deactivate')
        bulk_activate_action = menu.addAction('Bulk Activate')
        bulk_deactivate_action = menu.addAction('Bulk Deactivate')
        action = menu.exec(self.table.mapToGlobal(point))

        if action == edit_action:
            self.edit_selected_product()
        elif action == duplicate_action:
            self.duplicate_selected_product()
        elif action == delete_action:
            self.delete_selected_product()
        elif action == activate_action:
            self._set_selected_products_status('Active')
        elif action == deactivate_action:
            self._set_selected_products_status('Inactive')
        elif action == bulk_activate_action:
            self._set_selected_products_status('Active', bulk=True)
        elif action == bulk_deactivate_action:
            self._set_selected_products_status('Inactive', bulk=True)

    def _set_selected_products_status(self, status: str, bulk: bool = False):
        product_ids = self._selected_product_ids()
        if not product_ids:
            selected = self._selected_product()
            if selected:
                product_ids = [int(selected['id'])]
        if not product_ids:
            return

        if bulk and len(product_ids) < 2:
            QtWidgets.QMessageBox.information(self, 'Bulk Status Update', 'Select multiple rows for bulk update.')
            return

        try:
            update_products_status(product_ids, status)
            self.refresh_products()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Update Status', str(ex))

    def toggle_selected_product_status(self):
        product_ids = self._selected_product_ids()
        if not product_ids:
            return
        selected_products = [p for p in self.products if int(p.get('id', 0)) in set(product_ids)]
        if not selected_products:
            return
        if all((p.get('status', 'Active') or 'Active').lower() == 'active' for p in selected_products):
            self._set_selected_products_status('Inactive', bulk=len(product_ids) > 1)
        else:
            self._set_selected_products_status('Active', bulk=len(product_ids) > 1)

    def import_excel(self):
        action_dialog = QtWidgets.QMessageBox(self)
        action_dialog.setWindowTitle('Import Products')
        action_dialog.setText('Choose an action for product Excel import.')
        import_btn = action_dialog.addButton('Import Excel', QtWidgets.QMessageBox.AcceptRole)
        sample_btn = action_dialog.addButton('Download Sample Excel', QtWidgets.QMessageBox.ActionRole)
        action_dialog.addButton(QtWidgets.QMessageBox.Cancel)
        action_dialog.exec()

        clicked = action_dialog.clickedButton()
        if clicked == sample_btn:
            self.download_import_sample()
            return
        if clicked != import_btn:
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Import Products From Excel',
            str(ROOT),
            'Excel Files (*.xlsx *.xlsm)',
        )
        if not file_path:
            return
        try:
            report = import_products_from_excel(file_path)
            self.refresh_products()
            QtWidgets.QMessageBox.information(
                self,
                'Import Completed',
                f'Added: {report.added}\nUpdated: {report.updated}\nSkipped: {report.skipped}\nErrors: {report.errors}',
            )
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Import Products', str(ex))

    def download_import_sample(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Download Sample Product Excel',
            str(ROOT / 'products_import_sample.xlsx'),
            'Excel (*.xlsx)',
        )
        if not file_path:
            return
        try:
            generate_product_import_sample(file_path)
            QtWidgets.QMessageBox.information(self, 'Sample Generated', f'Sample file created at:\n{file_path}')
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, 'Sample Generation', str(ex))

    def export_products(self):
        menu = QtWidgets.QMenu(self)
        excel_action = menu.addAction('Export Excel (.xlsx)')
        csv_action = menu.addAction('Export CSV (.csv)')
        json_action = menu.addAction('Export JSON (.json)')
        action = menu.exec(QtGui.QCursor.pos())

        if action == excel_action:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export Excel', str(ROOT / 'products_export.xlsx'), 'Excel (*.xlsx)')
            if file_path:
                try:
                    export_products_excel(file_path)
                except Exception as ex:
                    QtWidgets.QMessageBox.warning(self, 'Export Excel', str(ex))
        elif action == csv_action:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export CSV', str(ROOT / 'products_export.csv'), 'CSV (*.csv)')
            if file_path:
                try:
                    export_products_csv(file_path)
                except Exception as ex:
                    QtWidgets.QMessageBox.warning(self, 'Export CSV', str(ex))
        elif action == json_action:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export JSON', str(ROOT / 'products_export.json'), 'JSON (*.json)')
            if file_path:
                try:
                    export_products_json(file_path)
                except Exception as ex:
                    QtWidgets.QMessageBox.warning(self, 'Export JSON', str(ex))

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, updated):
        self.settings = updated
        theme = self.settings.get('theme', self.current_theme)
        self.current_theme = theme
        self._apply_theme(theme)

    def publish(self):
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText('Publishing...')
        QtWidgets.QApplication.processEvents()

        try:
            def progress_cb(percent, message):
                self.progress.setValue(percent)
                self.status_label.setText(message)
                QtWidgets.QApplication.processEvents()

            result = publish_changes(progress_cb)
            QtWidgets.QMessageBox.information(
                self,
                'Publish Completed',
                f"Publish successful.\n\nBackup: {result['backup_path']}\nBranch: {result['branch']}\nDetails: {result['commit_output']}",
            )
        except Exception as ex:
            logger.exception('Publish failed')
            QtWidgets.QMessageBox.critical(self, 'Publish Failed', f'Publish failed.\n\n{ex}')
        finally:
            self.progress.setVisible(False)
            self.status_label.setText('Ready')
            self.refresh_products()

    def closeEvent(self, event):
        self._persist_table_layout()
        super().closeEvent(event)


def _handle_exception(exc_type, exc_value, exc_traceback):
    message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error('Unhandled exception:\n%s', message)
    QtWidgets.QMessageBox.critical(None, 'Unexpected Error', str(exc_value))


def main():
    sys.excepthook = _handle_exception
    app = QtWidgets.QApplication(sys.argv)
    window = AdminWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
