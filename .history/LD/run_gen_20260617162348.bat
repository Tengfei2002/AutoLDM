@echo off
setlocal

rem ================================================================
rem AutoLDM SDE generation entry
rem
rem Edit the four names below when switching input parameter files.
rem Use file names without suffix/path:
rem   LAYOUT_NAME     -> .\gds\%LAYOUT_NAME%_gds.txt
rem   ARCH_NAME       -> .\rules\%ARCH_NAME%_arch.txt
rem   LAYER_RULE_NAME -> .\rules\%LAYER_RULE_NAME%.txt
rem   OUTPUT_NAME     -> .\%OUTPUT_NAME%.cmd
rem ================================================================

set "LAYOUT_NAME=test1"
set "ARCH_NAME=cfet"
set "LAYER_RULE_NAME=layer_rule_1"
set "OUTPUT_NAME=gen_sde"

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "LAYOUT_FILE=.\gds\%LAYOUT_NAME%_gds.txt"
set "ARCH_FILE=.\rules\%ARCH_NAME%_arch.txt"
set "LAYER_RULE_FILE=.\rules\%LAYER_RULE_NAME%.txt"
set "OUTPUT_FILE=.\%OUTPUT_NAME%.cmd"

echo ================================================================
echo AutoLDM SDE generation
echo ================================================================
echo Layout file     : %LAYOUT_FILE%
echo Arch file       : %ARCH_FILE%
echo Layer rule file : %LAYER_RULE_FILE%
echo Output file     : %OUTPUT_FILE%
echo.

if not exist "%LAYOUT_FILE%" (
    echo [ERROR] Layout file not found: %LAYOUT_FILE%
    echo         Check LAYOUT_NAME or create the corresponding *_gds.txt file under .\gds.
    exit /b 1
)

if not exist "%ARCH_FILE%" (
    echo [ERROR] Architecture parameter file not found: %ARCH_FILE%
    echo         Check ARCH_NAME or create the corresponding *_arch.txt file under .\rules.
    exit /b 1
)

if not exist "%LAYER_RULE_FILE%" (
    echo [ERROR] Layer rule file not found: %LAYER_RULE_FILE%
    echo         Check LAYER_RULE_NAME or create the corresponding .txt file under .\rules.
    exit /b 1
)

echo Running gen_sde.py ...
python gen_sde.py "%LAYOUT_FILE%" "%ARCH_FILE%" "%LAYER_RULE_FILE%" "%OUTPUT_FILE%"

if errorlevel 1 (
    echo.
    echo [ERROR] gen_sde.py failed. See the Python error message above.
    exit /b 1
)

echo.
echo [OK] SDE command file generated: %OUTPUT_FILE%
endlocal
