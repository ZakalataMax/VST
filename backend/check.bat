@echo off
setlocal
cd /d "%~dp0"

set FAILED=0

echo [1/3] Python syntax...
python -m compileall -q app desktop
if errorlevel 1 set FAILED=1

echo [2/3] Import smoke test...
python -c "from desktop.widgets.report_panel import ReportPanel; from desktop.tabs.logs_tab import LogsTab; from app.services.file_report import run_report_pivot"
if errorlevel 1 set FAILED=1

echo [3/3] Pyright (app + desktop)...
python -m pyright app desktop
if errorlevel 1 set FAILED=1

if %FAILED%==1 (
  echo.
  echo CHECK FAILED
  exit /b 1
)

echo.
echo CHECK OK
endlocal
