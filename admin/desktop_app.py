import sys
import traceback
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from admin.database.db import init_db
from admin.services.catalog import (
    create_category,
    create_product,
    delete_category,
    delete_product,
    duplicate_product,
    export_products_csv,
    export_products_excel,
    export_products_json,
    get_settings,
    import_products_from_excel,
    list_categories,
    list_products,
    publish_changes,
    rename_category,
    update_product,
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
        self._build_ui()
        self._load_categories()
        if product:
            self._fill_form()

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
        self.description.setPlainText(self.product.get('description', ''))
        image_path = self.product.get('image_path', '')
        if image_path:
            self.image_info.setText(image_path)
            self._set_preview(str(ROOT / image_path.replace('/', '\\')))

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


class AdminWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.settings = get_settings()
        self.products = []
        self.current_theme = self.settings.get('theme', 'dark')
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

        self.add_btn.clicked.connect(self.add_product)
        self.edit_btn.clicked.connect(self.edit_selected_product)
        self.dup_btn.clicked.connect(self.duplicate_selected_product)
        self.del_btn.clicked.connect(self.delete_selected_product)
        self.refresh_btn.clicked.connect(self.refresh_products)
        self.import_btn.clicked.connect(self.import_excel)
        self.export_btn.clicked.connect(self.export_products)
        self.categories_btn.clicked.connect(self.manage_categories)

        for btn in [self.add_btn, self.edit_btn, self.dup_btn, self.del_btn, self.refresh_btn, self.import_btn, self.export_btn, self.categories_btn]:
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

        filters.addWidget(self.search, 3)
        filters.addWidget(self.category_filter, 1)
        filters.addWidget(self.min_price_filter, 1)
        filters.addWidget(self.max_price_filter, 1)
        filters.addWidget(self.stock_filter, 1)
        root.addLayout(filters)

        self.table = QtWidgets.QTableWidget(0, 13)
        self.table.setHorizontalHeaderLabels(
            [
                'Photo',
                'Product Name',
                'Category',
                'Purchase Price',
                'Selling Price',
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
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_product())
        root.addWidget(self.table)

        self.status_label = QtWidgets.QLabel('Ready')
        root.addWidget(self.status_label)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

    def _build_shortcuts(self):
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+N'), self, self.add_product)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+S'), self, self.publish)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+F'), self, self.focus_search)
        QtGui.QShortcut(QtGui.QKeySequence('Delete'), self, self.delete_selected_product)
        QtGui.QShortcut(QtGui.QKeySequence('F5'), self, self.refresh_products)

    def _apply_theme(self, theme: str):
        if theme == 'light':
            self.setStyleSheet('''
                QWidget { background: #f8fafc; color: #0f172a; }
                QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QTableWidget {
                    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px;
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
        id_item = self.table.item(row, 12)
        if not id_item:
            return None
        return int(id_item.text())

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
        )

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for product in self.products:
            row = self.table.rowCount()
            self.table.insertRow(row)

            image_widget = QtWidgets.QLabel()
            image_widget.setAlignment(QtCore.Qt.AlignCenter)
            image_widget.setFixedSize(58, 58)
            pix = QtGui.QPixmap(str(ROOT / product.get('image_path', '').replace('/', '\\')))
            if not pix.isNull():
                image_widget.setPixmap(pix.scaled(54, 54, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                image_widget.setText('N/A')
            self.table.setCellWidget(row, 0, image_widget)

            values = [
                product.get('product_name', ''),
                product.get('category', ''),
                f"{float(product.get('purchase_price', 0) or 0):.2f}",
                f"{float(product.get('selling_price', product.get('price', 0)) or 0):.2f}",
                f"{float(product.get('wholesale_price', 0) or 0):.2f}",
                product.get('barcode', ''),
                f"{float(product.get('gst', 0) or 0):.2f}",
                product.get('hsn', ''),
                f"{float(product.get('stock', 0) or 0):.2f}",
                f"{float(product.get('min_stock', 0) or 0):.2f}",
                product.get('description', ''),
                str(product.get('id', '')),
            ]
            for col, value in enumerate(values, start=1):
                item = QtWidgets.QTableWidgetItem(value)
                if col in {3, 4, 5, 7, 9, 10}:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, col, item)

            stock = float(product.get('stock', 0) or 0)
            min_stock = float(product.get('min_stock', 0) or 0)
            if stock <= 0:
                color = QtGui.QColor(127, 29, 29)
            elif stock <= min_stock:
                color = QtGui.QColor(120, 53, 15)
            else:
                color = QtGui.QColor(15, 23, 42)
            for col in range(1, 13):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(color)

        self.table.setSortingEnabled(True)
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
        create_product(dialog.payload(), dialog.image_source)
        self.refresh_products()

    def edit_selected_product(self):
        selected = self._selected_product()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Edit Product', 'Select a product to edit.')
            return
        dialog = ProductDialog(self, selected)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        update_product(selected['id'], dialog.payload(), dialog.image_source)
        self.refresh_products()

    def duplicate_selected_product(self):
        selected = self._selected_product()
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Duplicate Product', 'Select a product to duplicate.')
            return
        duplicate_product(selected['id'])
        self.refresh_products()

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
        delete_product(selected['id'])
        self.refresh_products()

    def manage_categories(self):
        dialog = CategoryDialog(self)
        dialog.changed.connect(self.refresh_products)
        dialog.exec()

    def show_context_menu(self, point):
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction('Edit')
        duplicate_action = menu.addAction('Duplicate')
        delete_action = menu.addAction('Delete')
        action = menu.exec(self.table.mapToGlobal(point))

        if action == edit_action:
            self.edit_selected_product()
        elif action == duplicate_action:
            self.duplicate_selected_product()
        elif action == delete_action:
            self.delete_selected_product()

    def import_excel(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Import Products From Excel',
            str(ROOT),
            'Excel Files (*.xlsx *.xlsm)',
        )
        if not file_path:
            return
        report = import_products_from_excel(file_path)
        self.refresh_products()
        QtWidgets.QMessageBox.information(
            self,
            'Import Completed',
            f'Added: {report.added}\nUpdated: {report.updated}\nSkipped: {report.skipped}\nErrors: {report.errors}',
        )

    def export_products(self):
        menu = QtWidgets.QMenu(self)
        excel_action = menu.addAction('Export Excel (.xlsx)')
        csv_action = menu.addAction('Export CSV (.csv)')
        json_action = menu.addAction('Export JSON (.json)')
        action = menu.exec(QtGui.QCursor.pos())

        if action == excel_action:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export Excel', str(ROOT / 'products_export.xlsx'), 'Excel (*.xlsx)')
            if file_path:
                export_products_excel(file_path)
        elif action == csv_action:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export CSV', str(ROOT / 'products_export.csv'), 'CSV (*.csv)')
            if file_path:
                export_products_csv(file_path)
        elif action == json_action:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export JSON', str(ROOT / 'products_export.json'), 'JSON (*.json)')
            if file_path:
                export_products_json(file_path)

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
