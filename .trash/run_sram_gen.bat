@echo off
setlocal

rem ================================================================
rem AutoLDM 6T SRAM SDE generation entry
rem
rem Edit the names below when switching architecture.
rem Use file names without suffix/path:
rem   SRAM_NAME       -> .\gds\%SRAM_NAME%_gds.txt
rem   ARCH_NAME       -> .\rules\%ARCH_NAME%_arch.txt
rem   LAYER_RULE_NAME -> .\rules\%LAYER_RULE_NAME%.txt
rem   OUTPUT_NAME     -> .\SDE\%OUTPUT_NAME%_sde.cmd
rem ================================================================

set "SRAM_NAME=sram_6t_scfet"
set "ARCH_NAME=sram_scfet"
set "LAYER_RULE_NAME=sram_scfet_layer_rule"
set "OUTPUT_NAME=%SRAM_NAME%"

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "LAYOUT_FILE=.\gds\%SRAM_NAME%_gds.txt"
set "ARCH_FILE=.\rules\%ARCH_NAME%_arch.txt"
set "LAYER_RULE_FILE=.\rules\%LAYER_RULE_NAME%.txt"
set "OUTPUT_DIR=.\SDE"
set "OUTPUT_FILE=%OUTPUT_DIR%\%OUTPUT_NAME%_sde.cmd"
set "GDS_FILE=.\gds\%SRAM_NAME%.gds"

echo ================================================================
echo AutoLDM SRAM SDE generation
echo ================================================================
echo Layout file     : %LAYOUT_FILE%
echo Arch file       : %ARCH_FILE%
echo Layer rule file : %LAYER_RULE_FILE%
echo Output file     : %OUTPUT_FILE%
echo GDS file        : %GDS_FILE%
echo.

if not exist "%LAYOUT_FILE%" (
    echo [ERROR] Layout file not found: %LAYOUT_FILE%
    exit /b 1
)

if not exist "%ARCH_FILE%" (
    echo [ERROR] Architecture parameter file not found: %ARCH_FILE%
    exit /b 1
)

if not exist "%LAYER_RULE_FILE%" (
    echo [ERROR] Layer rule file not found: %LAYER_RULE_FILE%
    exit /b 1
)

if not exist "%OUTPUT_DIR%" (
    mkdir "%OUTPUT_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create output directory: %OUTPUT_DIR%
        exit /b 1
    )
)

echo Running gen_sram_sde.py ...
echo Validating layout tracks and geometry ...
python validate_sram_layout.py "%LAYOUT_FILE%" "%ARCH_FILE%"

if errorlevel 1 (
    echo.
    echo [ERROR] SRAM layout validation failed.
    exit /b 1
)

python gen_sram_sde.py "%LAYOUT_FILE%" "%ARCH_FILE%" "%LAYER_RULE_FILE%" "%OUTPUT_FILE%"

if errorlevel 1 (
    echo.
    echo [ERROR] gen_sram_sde.py failed. See the Python error message above.
    exit /b 1
)

echo Generating GDSII from layout TXT ...
python txt_to_gds.py "%LAYOUT_FILE%" "%GDS_FILE%"

if errorlevel 1 (
    echo.
    echo [ERROR] GDSII generation failed.
    exit /b 1
)

echo Generating frontside, backside, and mixed layout views ...
python draw_sram_layout.py "%LAYOUT_FILE%" "%ARCH_FILE%" ".\layout_views"

if errorlevel 1 (
    echo.
    echo [ERROR] Layout view generation failed.
    exit /b 1
)

echo.
echo [OK] SRAM SDE command file generated: %OUTPUT_FILE%
echo [OK] SRAM GDSII generated: %GDS_FILE%
echo [OK] Layout views generated under: .\layout_views
endlocal
