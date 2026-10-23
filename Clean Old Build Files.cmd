@echo off
setlocal
if not exist "%~dp0.local\cleanup-20261023\plan.json" (
  echo A reviewed local cleanup plan is not available. Request a fresh cleanup review.
  pause
  exit /b 1
)
if not exist "%~dp0.local\cleanup-20261023\Run-Reviewed-Cleanup.cmd" (
  echo The guarded local cleanup runner is not available.
  pause
  exit /b 1
)
echo This removes about 119 MiB of reviewed old compiler intermediates only.
echo Qualified evidence, game inputs and the current build are retained.
call "%~dp0.local\cleanup-20261023\Run-Reviewed-Cleanup.cmd"
exit /b %ERRORLEVEL%
