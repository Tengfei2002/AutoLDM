param(
    [string]$HspiceCmd = "",
    [string]$InstallDir = "",
    [string]$LicenseServer = "",
    [switch]$SkipSram,
    [switch]$SkipSingle,
    [switch]$PlotOnly
)

$ErrorActionPreference = "Stop"

$IvDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $IvDir "..\..")
$Runner = Join-Path $RepoRoot "Hspice\iv_flow\run_hspice.py"
$ResultsDir = Join-Path $IvDir "results"
$PngDir = Join-Path $IvDir "png"
$Plotter = Join-Path $IvDir "plot_hspice_results.py"

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
New-Item -ItemType Directory -Force -Path $PngDir | Out-Null

function Invoke-Deck {
    param([string]$DeckPath)

    $args = @($Runner, $DeckPath, "--results-dir", $ResultsDir)
    if (-not [string]::IsNullOrWhiteSpace($HspiceCmd)) {
        $args += @("--hspice-cmd", $HspiceCmd)
    }
    if (-not [string]::IsNullOrWhiteSpace($InstallDir)) {
        $args += @("--install-dir", $InstallDir)
    }
    if (-not [string]::IsNullOrWhiteSpace($LicenseServer)) {
        $args += @("--license-server", $LicenseServer)
    }

    Write-Host ""
    Write-Host "Running HSPICE deck:"
    Write-Host "  $DeckPath"
    python @args
    if ($LASTEXITCODE -ne 0) {
        throw "HSPICE failed for $DeckPath with exit code $LASTEXITCODE"
    }
}

if (-not $PlotOnly) {
    if (-not $SkipSram) {
        Invoke-Deck (Join-Path $RepoRoot "output_SDE\rc_sp\standard_sram.sp")
    }

    if (-not $SkipSingle) {
        $singleDecks = @(
            "single_va_nmos_idvg.sp",
            "single_va_nmos_idvd.sp",
            "single_va_pmos_idvg.sp",
            "single_va_pmos_idvd.sp"
        )

        foreach ($deck in $singleDecks) {
            Invoke-Deck (Join-Path $IvDir $deck)
        }
    }
}

Write-Host ""
Write-Host "Generating PNG figures:"
Write-Host "  $PngDir"
python $Plotter --results $ResultsDir --png $PngDir
if ($LASTEXITCODE -ne 0) {
    throw "Plotting failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done."
Write-Host "HSPICE results: $ResultsDir"
Write-Host "PNG figures:    $PngDir"
