param(
    [switch]$DryRun,
    [switch]$GenerateOnly,
    [switch]$NoPlot
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InputRoot = Join-Path $ProjectRoot "INPUT_MODEL"
$SdeRoot = Join-Path $ProjectRoot "SDE"
$OutputRoot = Join-Path $ProjectRoot "OUTPUT"
$HspiceRoot = Join-Path $ProjectRoot "Hspice"
$Name = "inv_test"
$CellType = "inv"

python (Join-Path $ProjectRoot "gen_sde.py") `
    (Join-Path $InputRoot "${Name}_gds.txt") `
    (Join-Path $InputRoot "${Name}_params.txt") `
    (Join-Path $InputRoot "${Name}_stacked.txt") `
    --design-rules (Join-Path $InputRoot "${Name}_design_rules.txt") `
    --c-output (Join-Path $SdeRoot "${Name}_c_sde.cmd") `
    -o (Join-Path $SdeRoot "${Name}_r_sde.cmd")
if ($LASTEXITCODE -ne 0) { throw "SDE generation failed: $LASTEXITCODE" }

python (Join-Path $ProjectRoot "gen_drc_report.py") `
    (Join-Path $InputRoot "${Name}_gds.txt") `
    (Join-Path $InputRoot "${Name}_params.txt") `
    (Join-Path $InputRoot "${Name}_stacked.txt") `
    (Join-Path $InputRoot "${Name}_design_rules.txt") `
    -o (Join-Path $OutputRoot "${Name}_drc_report.txt")
if ($LASTEXITCODE -ne 0) { throw "DRC generation failed: $LASTEXITCODE" }

$CellArguments = @(
    (Join-Path $ProjectRoot "run_cell.py"),
    "--name", $Name,
    "--cell", $CellType,
    "--input-model-dir", $InputRoot,
    "--c-matrix", (Join-Path $SdeRoot "${Name}_c_cMatrix.spi"),
    "--r-matrix", (Join-Path $SdeRoot "${Name}_r_cMatrix.spi"),
    "--n-va", (Join-Path $InputRoot "${Name}_fet_n.va"),
    "--p-va", (Join-Path $InputRoot "${Name}_fet_p.va"),
    "--output", $HspiceRoot,
    "--strict-contact-face"
)
if ($DryRun) { $CellArguments += "--dry-run" }
if ($GenerateOnly) { $CellArguments += "--generate-only" }
if ($NoPlot) { $CellArguments += "--no-plot" }

python @CellArguments
if ($LASTEXITCODE -ne 0) { throw "INV PEX/HSPICE flow failed: $LASTEXITCODE" }
