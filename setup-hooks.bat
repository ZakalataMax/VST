@echo off
setlocal
cd /d "%~dp0"
git config core.hooksPath .githooks
echo Git hooks path set to .githooks
echo pre-push will run backend parser tests before each push.
