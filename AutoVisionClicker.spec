# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: bundles the Poké Ball template and a full copy of adb so the .exe
# is self-contained (no separate adb install required on the target PC).

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates/pokeball.png', 'templates'),
        ('templates/camera.png', 'templates'),
        ('templates/nearby_anchor.png', 'templates'),
        ('templates/menu_star.png', 'templates'),
        ('templates/popup_autowalk.png', 'templates'),
        ('templates/popup_speed.png', 'templates'),
        ('adb/adb.exe', 'adb'),
        ('adb/AdbWinApi.dll', 'adb'),
        ('adb/AdbWinUsbApi.dll', 'adb'),
        ('adb/libwinpthread-1.dll', 'adb'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutoVisionClicker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
