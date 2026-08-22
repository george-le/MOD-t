# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['software/modt_app.py'],
    pathex=[],
    binaries=[('/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib', '.')],
    datas=[],
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
    [],
    exclude_binaries=True,
    name='MOD-t_Printer_Utility',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
   icon='software/assets/windows/modt_app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MOD-t_Printer_Utility_windows',
)
app = BUNDLE(
    coll,
    name='MOD-t Printer Utility.app',
    icon='software/assets/macos/modt_app_icon.icns',
    bundle_identifier=None,
)
