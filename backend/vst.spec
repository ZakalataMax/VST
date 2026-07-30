# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

backend_dir = Path(SPECPATH).resolve()
block_cipher = None

duckdb_datas, duckdb_binaries, duckdb_hidden = collect_all("duckdb")
openpyxl_datas, openpyxl_binaries, openpyxl_hidden = collect_all("openpyxl")
numpy_datas, numpy_binaries, numpy_hidden = collect_all("numpy")

stdlib_hiddenimports = [
    "uuid",
    "_uuid",
    "decimal",
    "datetime",
    "json",
    "zlib",
    "encodings.idna",
]

win32_hiddenimports = [
    "win32com",
    "win32com.client",
    "win32com.client.dynamic",
    "pythoncom",
    "pywintypes",
]

hiddenimports = [
    "openpyxl",
    "openpyxl.cell",
    "openpyxl.cell._writer",
    "openpyxl.workbook",
    "openpyxl.worksheet._writer",
    "desktop.main_window",
    "desktop.tabs.parser_tab",
    "desktop.tabs.logs_tab",
    "desktop.workers",
    "desktop.parsing_tools",
    "desktop.coverage_utils",
    "desktop.report_sql_utils",
    "desktop.theme",
    "desktop.widgets.common",
    "desktop.widgets.coverage_sidebar",
    "desktop.widgets.import_parse_panel",
    "desktop.widgets.report_panel",
    "desktop.report_table_utils",
    "app.parsers.acs_log_parser",
    "app.parsers.csv_writer",
    "app.parsers.field_mapping",
    "app.parsers.models",
    "app.parsers.patterns",
    "app.services.file_report",
    "app.services.log_storage",
    "app.services.csv_storage",
    "app.services.elastic_logs",
    "app.services.report",
    "app.services.excel_pivot",
    "app.services.outlook_sender",
    "app.services.report_mailer",
    "app.jobs.daily_report",
    "app.paths",
    "app.config",
] + stdlib_hiddenimports + duckdb_hidden + openpyxl_hidden + numpy_hidden + win32_hiddenimports

a = Analysis(
    [str(backend_dir / "desktop" / "__main__.py")],
    pathex=[str(backend_dir)],
    binaries=duckdb_binaries + openpyxl_binaries + numpy_binaries,
    datas=[
        (str(backend_dir / "db" / "report_query.sql"), "db"),
        (str(backend_dir / "app" / "data" / "android_model_aliases.json"), "app/data"),
    ]
    + duckdb_datas
    + openpyxl_datas
    + numpy_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(backend_dir / "desktop" / "pyi_rth_preload.py")],
    excludes=[
        "duckdb.experimental",
        "duckdb.experimental.spark",
        "duckdb.query_graph",
        "duckdb.polars_io",
        "duckdb.filesystem",
        "duckdb.udf",
    ],
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
    name="VST",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
