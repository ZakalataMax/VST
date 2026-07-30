@echo off
cd /d "%~dp0"

if not exist "%~dp0data" mkdir "%~dp0data"
set "LOG_FILE=%~dp0data\auto_report.log"
set "REPORT_EMAIL_TO=d.bulgakov@ornament-soft.com, o.stolyar@vstbank.ua"

echo. >> "%LOG_FILE%"
echo ===== %date% %time% : starting VST auto-report (dist\VST.exe) ===== >> "%LOG_FILE%"
"%~dp0dist\VST.exe" --auto-report >> "%LOG_FILE%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo ===== %date% %time% : finished with exit code %EXITCODE% ===== >> "%LOG_FILE%"
exit /b %EXITCODE%
