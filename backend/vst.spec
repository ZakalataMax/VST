# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

backend_dir = Path(SPECPATH).resolve()
block_cipher = None

duckdb_datas, duckdb_binaries, duckdb_hidden = collect_all("duckdb")
openpyxl_datas, openpyxl_binaries, openpyxl_hidden = collect_all("openpyxl")
numpy_datas, numpy_binaries, numpy_hidden = collect_all("numpy")
tzdata_datas, tzdata_binaries, tzdata_hidden = collect_all("tzdata")

stdlib_hiddenimports = [
    "uuid",
    "_uuid",
    "decimal",
    "datetime",
    "json",
    "zlib",
    "encodings.idna",
    "zoneinfo",
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
    "desktop.theme",
    "desktop.widgets.common",
    "desktop.tools.acs.acs_tab",
    "desktop.tools.acs.workers",
    "desktop.tools.acs.coverage_utils",
    "desktop.tools.acs.report_sql_utils",
    "desktop.tools.acs.report_table_utils",
    "desktop.tools.acs.widgets.coverage_sidebar",
    "desktop.tools.acs.widgets.import_parse_panel",
    "desktop.tools.acs.widgets.report_panel",
    "desktop.tools.threeds.threeds_tab",
    "desktop.tools.threeds.workers",
    "desktop.tools.threeds.coverage",
    "desktop.tools.threeds.report_sql_utils",
    "desktop.tools.threeds.report_table_utils",
    "desktop.tools.threeds.widgets.coverage_sidebar",
    "desktop.tools.threeds.widgets.download_panel",
    "desktop.tools.threeds.widgets.log_viewer",
    "desktop.tools.threeds.widgets.report_panel",
    "desktop.tools.parser.parser_tab",
    "desktop.tools.parser.parsing_tools",
    "app.common.config",
    "app.common.paths",
    "app.common.elastic_logs",
    "app.common.device_detection",
    "app.common.excel_pivot",
    "app.common.parse_diagnostics",
    "app.common.duckdb_time_zone",
    "app.common.report_utils",
    "app.acs.paths",
    "app.acs.elastic_config",
    "app.acs.parsers.acs_log_parser",
    "app.acs.parsers.csv_writer",
    "app.acs.parsers.field_mapping",
    "app.acs.parsers.models",
    "app.acs.parsers.patterns",
    "app.acs.services.file_report",
    "app.acs.services.log_storage",
    "app.acs.services.csv_storage",
    "app.acs.services.report",
    "app.acs.services.card_champions",
    "app.acs.services.outlook_sender",
    "app.acs.services.report_mailer",
    "app.acs.jobs.daily_report",
    "app.threeds.paths",
    "app.threeds.elastic_config",
    "app.threeds.log_storage",
    "app.threeds.parsers.threeds_log_parser",
    "app.threeds.parsers.csv_writer",
    "app.threeds.parsers.field_mapping",
    "app.threeds.parsers.models",
    "app.threeds.parsers.patterns",
    "app.threeds.services.csv_storage",
    "app.threeds.services.file_report",
] + stdlib_hiddenimports + duckdb_hidden + openpyxl_hidden + numpy_hidden + tzdata_hidden + win32_hiddenimports

a = Analysis(
    [str(backend_dir / "desktop" / "__main__.py")],
    pathex=[str(backend_dir)],
    binaries=duckdb_binaries + openpyxl_binaries + numpy_binaries + tzdata_binaries,
    datas=[
        (str(backend_dir / "db" / "report_query.sql"), "db"),
        (str(backend_dir / "db" / "report_query_3ds.sql"), "db"),
        (str(backend_dir / "app" / "data" / "android_model_aliases.json"), "app/data"),
    ]
    + duckdb_datas
    + openpyxl_datas
    + numpy_datas
    + tzdata_datas,
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
