# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

added_files = [
    ("config", "config"),
    ("ui", "ui"),
]

# Include bundled Tesseract if present in tools/tesseract/
_tess_src = os.path.join(os.path.abspath("."), "tools", "tesseract")
if os.path.isdir(_tess_src):
    added_files.append((_tess_src, "tesseract"))

a = Analysis(
    ["main.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "pdfplumber",
        "pytesseract",
        "PIL",
        "pdf2image",
        "pandas",
        "numpy",
        "watchdog",
        "PyQt6",
        "openpyxl",
        "reportlab",
        "core.extractor",
        "core.ocr",
        "core.parser",
        "core.classifier",
        "core.watcher",
        "data.models",
        "data.processor",
        "data.validator",
        "export.excel_exporter",
        "export.pdf_reporter",
        "export.email_sender",
        "ui.main_window",
        "ui.dashboard",
        "ui.table_view",
        "ui.log_panel",
        "ui.settings_dialog",
        "ui.components.sidebar",
        "ui.components.progress_bar",
        "ui.components.flag_badge",
        "ui.components.language_toggle",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AnalyzenInvoiceReader",
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
    icon=None,
)
