#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Installing build dependencies..."
python -m pip install -r requirements.txt pyinstaller

echo "==> Building VST.exe..."
python -m PyInstaller vst.spec --noconfirm --clean

if [ -f ".env" ]; then
  cp ".env" "dist/.env"
  echo "==> Copied .env next to VST.exe"
fi

echo ""
echo "Done: $(pwd)/dist/VST.exe"
echo "Data folder is created next to the exe: data/logs, data/csv, data/csv_reports_final"
echo "ELASTIC_PASS is read from dist/.env (copied from backend/.env), or from the environment."
