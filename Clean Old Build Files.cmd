@echo off
setlocal
cd /d "%~dp0"
echo Ys III build cleanup - progress and results will appear below.
echo Game inputs, native source, executables and qualification evidence are retained.
python -u "%~dp0scripts\clean_build_files.py" %*
set "YS3_CLEAN_EXIT=%ERRORLEVEL%"
echo.
echo Cleanup exit code: %YS3_CLEAN_EXIT%
if /i "%~1"=="--no-pause" exit /b %YS3_CLEAN_EXIT%
pause
exit /b %YS3_CLEAN_EXIT%
