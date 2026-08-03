# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: bundles the Poké Ball template and a full copy of adb so the .exe
# is self-contained (no separate adb install required on the target PC).

import os


# The bundled build Python has the Tcl/Tk DLLs but no conventional ``tcl`` directory.
# Point PyInstaller's tkinter hook at the checked-in runtime data so clean local builds do
# not silently exclude tkinter and produce an EXE that fails before the GUI can open.
_tcl_root = os.path.join(SPECPATH, 'build-tcl-runtime')
_tcl_library = os.path.join(_tcl_root, 'tcl8.6')
_tk_library = os.path.join(_tcl_root, 'tk8.6')
if os.path.isfile(os.path.join(_tcl_library, 'init.tcl')):
    os.environ['TCL_LIBRARY'] = _tcl_library
if os.path.isfile(os.path.join(_tk_library, 'tk.tcl')):
    os.environ['TK_LIBRARY'] = _tk_library


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates/*.png', 'templates'),
        ('adb/adb.exe', 'adb'),
        ('adb/AdbWinApi.dll', 'adb'),
        ('adb/AdbWinUsbApi.dll', 'adb'),
        ('adb/libwinpthread-1.dll', 'adb'),
        ('tools/scrcpy-server-v4.0', 'tools'),
        ('tools/scrcpy-LICENSE.txt', 'tools'),
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
    name='AutoCatchPokemonPGSharp',
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
