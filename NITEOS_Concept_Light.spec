# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['facade_concept_gui_v139.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('examples', 'examples'),
    ],
    hiddenimports=[
        'ai_packager_v29',
        'customtkinter',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NITEOS_Concept_Light',
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
    icon='assets/niteos_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NITEOS_Concept_Light',
)
