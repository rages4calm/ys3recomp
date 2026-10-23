@echo off
setlocal
cd /d "%~dp0"
python "%~dp0scripts\play_local.py" %*
if errorlevel 1 pause
