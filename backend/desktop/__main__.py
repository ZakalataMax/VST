from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from app.config import env_file_path, load_env_file

load_env_file()


def _crash_log_path() -> Path:
    return env_file_path().parent / "vst-error.log"


def _log_crash(message: str) -> None:
    try:
        with _crash_log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"\n===== {datetime.now().isoformat()} =====\n")
            handle.write(message)
            handle.write("\n")
    except OSError:
        pass


def _install_crash_logging() -> None:
    def hook(exc_type, exc, tb) -> None:
        _log_crash("".join(traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> None:
    _install_crash_logging()
    try:
        if "--auto-report" in sys.argv[1:]:
            from app.jobs.daily_report import main as run_daily_job

            sys.exit(run_daily_job())

        from desktop.main_window import main as run_app

        run_app()
    except Exception:
        _log_crash(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
