@echo off
setlocal
set "FLOW_DIR=%~dp0.."
python "%FLOW_DIR%\run_wv.py" %*
exit /b %ERRORLEVEL%
