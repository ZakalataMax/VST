# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

backend_dir = Path(SPECPATH).resolve()
block_cipher = None

duckdb_datas, duckdb_binaries, duckdb_hidden = collect_all("duckdb")

hiddenimports = [
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
    "app.parsers.acs_log_parser",
    "app.parsers.csv_writer",
    "app.parsers.field_mapping",
    "app.parsers.models",
    "app.parsers.patterns",
    "app.services.file_report",
    "app.services.log_storage",
    "app.services.csv_storage",
    "app.services.report",
    "app.paths",
] + duckdb_hidden

a = Analysis(
    [str(backend_dir / "desktop" / "__main__.py")],
    pathex=[str(backend_dir)],
    binaries=duckdb_binaries,
    datas=[
        (str(backend_dir / "db" / "report_query.sql"), "db"),
    ]
    + duckdb_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "test", "tests"],
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
