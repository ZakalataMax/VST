from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env_next_to_exe() -> None:
    if not getattr(sys, "frozen", False):
        return
    env_path = Path(sys.executable).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_next_to_exe()

from desktop.main_window import main

if __name__ == "__main__":
    main()
