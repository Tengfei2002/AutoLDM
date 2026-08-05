@echo off
setlocal
set "FLOW_DIR=%~dp0.."
python "%FLOW_DIR%\run_hspice.py" %*
exit /b %ERRORLEVEL%
