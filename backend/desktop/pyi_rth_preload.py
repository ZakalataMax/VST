import importlib
import sys

for module_name in ("uuid", "_uuid", "decimal", "datetime", "json", "zlib"):
    try:
        importlib.import_module(module_name)
    except ImportError:
        pass

if getattr(sys, "frozen", False):
    try:
        import duckdb  # noqa: F401
    except ImportError:
        pass
