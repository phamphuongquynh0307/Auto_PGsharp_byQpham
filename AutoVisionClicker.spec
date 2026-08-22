# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: bundles the Poké Ball template and a full copy of adb so the .exe
# is self-contained (no separate adb install required on the target PC).

import os


# Some build Pythons ship the Tcl/Tk DLLs but no conventional ``tcl`` directory, and
# PyInstaller then quietly drops tkinter — producing an EXE that dies on ``import tkinter``
# before the GUI can open. The checked-in runtime data is the fallback for those.
#
# It is only a *fallback*. Forcing TCL_LIBRARY/TK_LIBRARY at an interpreter that already
# knows where its own Tcl lives breaks the very thing it was meant to fix: PyInstaller
# probes Tcl/Tk in a child process that inherits these variables, the pointed-at runtime
# does not match the loaded DLLs, the probe fails, and the hook excludes tkinter with a
# one-line warning buried in the build log. So ask first, and only step in when the answer
# is that Tcl/Tk genuinely cannot start.
def _tcl_tk_starts() -> bool:
    root = None
    try:
        import tkinter
        # ``tkinter.Tcl()`` alone only proves that the DLL loads.  A Python runtime can
        # still be missing init.tcl/tk.tcl, in which case the bundled EXE starts but never
        # creates its window.  Construct the same Tk root the application needs, hide it
        # immediately, and fall back to the checked-in scripts if that fails.
        root = tkinter.Tk()
        root.withdraw()
        return True
    except Exception:
        return False
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


if not _tcl_tk_starts():
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
        # Ship the complete in-app guide with the one-file EXE.  The GUI still checks a
        # guide_images folder beside the EXE first, so a newer screenshot can override a
        # bundled one without rebuilding the application.
        ('guide_images/*.png', 'guide_images'),
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
    # Some Windows security configurations let the bootloader extract into %TEMP% but
    # prevent Tcl/Tk from sourcing init.tcl there.  The documented install folder is
    # writable, so unpack the one-file runtime in the launch working directory instead.
    runtime_tmpdir='.',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
