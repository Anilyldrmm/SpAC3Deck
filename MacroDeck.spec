# -*- mode: python ; coding: utf-8 -*-
import glob
import os
import sys
import zipfile


def _tcl9_datas():
    # Python 3.14 (Tcl/Tk 9) kutuphanelerini zip icinde tasir; PyInstaller bunlari
    # tanimiyor, _tcl_data/_tk_data eksik kalinca exe acilista sessizce olur.
    # Tcl 8.6 (eski Python) ile zip yok, bu fonksiyon bos doner.
    # shortcut: sadece Tcl 9 zip duzeni, baska bir duzen gelirse exe'yi acip dogrula.
    out = []
    root = os.path.join(sys.base_prefix, "tcl")
    for pattern, inner, dest in (("libtcl9*.zip", "tcl_library", "_tcl_data"), ("libtk9*.zip", "tk_library", "_tk_data")):
        found = glob.glob(os.path.join(root, pattern))
        if not found:
            continue
        target = os.path.join(SPECPATH, "build", "tcl9")
        with zipfile.ZipFile(found[0]) as z:
            z.extractall(target, [n for n in z.namelist() if n.startswith(inner + "/")])
        out.append((os.path.join(target, inner), dest))
    return out


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')] + _tcl9_datas(),
    hiddenimports=['tkinter'],  # OSD penceresi tkinter kullanir (fonksiyon icinde import ediliyor)
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
    name='MacroDeck',
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
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MacroDeck',
)
