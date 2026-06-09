from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH_DIRS = (ROOT / "desktop", ROOT / "app")
WATCH_FILES = (ROOT / "db" / "report_query.sql",)
POLL_SECONDS = 0.5
DEBOUNCE_SECONDS = 0.35


def _iter_watch_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in WATCH_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            paths.append(path)
    for path in WATCH_FILES:
        if path.is_file():
            paths.append(path)
    return paths


def _snapshot() -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for path in _iter_watch_paths():
        try:
            snapshot[str(path)] = path.stat().st_mtime
        except OSError:
            continue
    return snapshot


def _start_app() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "desktop"], cwd=ROOT)


def _stop_app(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def main() -> int:
    print("VST dev watch — edit and save .py files to reload. Ctrl+C to stop.")
    snapshot = _snapshot()
    proc = _start_app()
    try:
        while True:
            time.sleep(POLL_SECONDS)
            if proc.poll() is not None:
                print("App exited, restarting…")
                proc = _start_app()
                snapshot = _snapshot()
                continue

            current = _snapshot()
            if current == snapshot:
                continue

            time.sleep(DEBOUNCE_SECONDS)
            confirmed = _snapshot()
            if confirmed == snapshot:
                continue

            print("Changes detected, restarting…")
            snapshot = confirmed
            _stop_app(proc)
            proc = _start_app()
    except KeyboardInterrupt:
        print("\nStopping…")
        _stop_app(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
