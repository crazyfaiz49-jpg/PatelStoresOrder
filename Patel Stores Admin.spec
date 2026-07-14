# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['admin\\desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[('admin', 'admin'), ('images', 'images'), ('products.json', '.'), ('patelstores.db', '.'), ('backup', 'backup')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Patel Stores Admin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['release\\PatelStores.ico'],
)
