from PyInstaller.utils.hooks import collect_all, collect_data_files

ortools_data, ortools_binaries, ortools_hidden = collect_all("ortools")

a = Analysis(
    ["scheduler_gui.py"],
    pathex=[],
    binaries=ortools_binaries,
    datas=ortools_data + collect_data_files("pylatex"),
    hiddenimports=ortools_hidden,
    hookspath=["pyinstaller_hooks"],
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
    name="FLL Schedule Generator",
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
)
