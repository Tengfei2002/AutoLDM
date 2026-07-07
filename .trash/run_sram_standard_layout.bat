@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "LAYOUT_FILE=.\gds\sram_standard_6t_gds.txt"
set "ARCH_FILE=.\rules\sram_standard_arch.txt"
set "MAX_LAYOUT_FILE=.\gds\sram_standard_max_layout_gds.txt"
set "LAYER_RULE_FILE=.\rules\sram_standard_layer_rule.txt"
set "GDS_FILE=.\gds\sram_standard_6t.gds"
set "MAX_GDS_FILE=.\gds\sram_standard_max_layout.gds"
set "VIEW_DIR=.\layout_views"
set "SDE_DIR=.\SDE"
set "SDE_FILE=%SDE_DIR%\sram_standard_6t_sde.cmd"

for %%F in ("%LAYOUT_FILE%" "%ARCH_FILE%" "%MAX_LAYOUT_FILE%" "%LAYER_RULE_FILE%") do (
    if not exist "%%~F" (
        echo [ERROR] Missing input: %%~F
        exit /b 1
    )
)

echo Validating sram_standard layout...
python validate_sram_standard_layout.py "%LAYOUT_FILE%" "%ARCH_FILE%"
if errorlevel 1 exit /b 1

echo Generating GDSII files...
python txt_to_gds.py "%LAYOUT_FILE%" "%GDS_FILE%"
if errorlevel 1 exit /b 1
python txt_to_gds.py "%MAX_LAYOUT_FILE%" "%MAX_GDS_FILE%"
if errorlevel 1 exit /b 1

echo Generating layout views...
python draw_sram_standard_layout.py "%LAYOUT_FILE%" "%ARCH_FILE%" "%VIEW_DIR%"
if errorlevel 1 exit /b 1

if not exist "%SDE_DIR%" mkdir "%SDE_DIR%"

echo Generating Sentaurus SDE command...
python gen_sram_standard_sde.py "%LAYOUT_FILE%" "%ARCH_FILE%" "%LAYER_RULE_FILE%" "%SDE_FILE%"
if errorlevel 1 exit /b 1

echo [OK] sram_standard TXT, GDSII, PNG and SDE CMD outputs are current.
endlocal
