@echo off
setlocal
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

echo Building VST.exe...
python -m PyInstaller vst.spec --noconfirm --clean
if errorlevel 1 exit /b 1

echo.
echo Done: %~dp0dist\VST.exe
echo Data folder will be created next to the exe: data\logs, data\csv, data\csv_reports_final
echo You can create a desktop shortcut to dist\VST.exe
endlocal
