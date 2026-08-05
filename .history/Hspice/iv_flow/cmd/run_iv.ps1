param(
    [ValidateSet("all", "single", "circuit", "nmos", "pmos")]
    [string]$Target = "all",
    [string]$HspiceCmd = "",
    [string]$InstallDir = "",
    [string]$LicenseServer = "",
    [string]$RunName = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FlowDir = Split-Path -Parent $ScriptDir
$DeckDir = Join-Path $FlowDir "decks"
$ResultsRoot = Join-Path $FlowDir "results"

if ([string]::IsNullOrWhiteSpace($HspiceCmd)) {
    if ([string]::IsNullOrWhiteSpace($InstallDir)) {
        $candidateInstallDirs = @(
            "C:\synopsys\Hspice_P-2019.06-SP1-1",
            "C:\synopsys\Hspice_O-2018.09"
        )
        foreach ($candidate in $candidateInstallDirs) {
            if ((Test-Path -LiteralPath (Join-Path $candidate "WIN64\hspice.com")) -or
                (Test-Path -LiteralPath (Join-Path $candidate "WIN64\hspice.exe"))) {
                $InstallDir = $candidate
                break
            }
        }
    }

    $localHspiceCom = Join-Path $InstallDir "WIN64\hspice.com"
    $localHspiceExe = Join-Path $InstallDir "WIN64\hspice.exe"

    if (Test-Path -LiteralPath $localHspiceCom) {
        $HspiceCmd = $localHspiceCom
    }
    elseif (Test-Path -LiteralPath $localHspiceExe) {
        $HspiceCmd = $localHspiceExe
    }
    else {
        $command = Get-Command hspice -ErrorAction SilentlyContinue
        if ($command) {
            $HspiceCmd = $command.Source
        }
        else {
            throw "Cannot find HSPICE. Pass -HspiceCmd or check -InstallDir."
        }
    }
}

if (Test-Path -LiteralPath $InstallDir) {
    Set-Item -Path Env:'installdir_O-2018.09' -Value $InstallDir
    Set-Item -Path Env:'installdir_P-2019.06-SP1-1' -Value $InstallDir
}

if (-not [string]::IsNullOrWhiteSpace($LicenseServer)) {
    $env:SNPSLMD_LICENSE_FILE = $LicenseServer
}

if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = Get-Date -Format "yyyyMMdd_HHmmss"
}

$RunDir = Join-Path $ResultsRoot $RunName
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

$deckMap = @{
    "nmos"    = @("single_nmos_output_iv.sp")
    "pmos"    = @("single_pmos_output_iv.sp")
    "single"  = @("single_nmos_output_iv.sp", "single_pmos_output_iv.sp")
    "circuit" = @("circuit_inverter_dc_iv.sp")
    "all"     = @("single_nmos_output_iv.sp", "single_pmos_output_iv.sp", "circuit_inverter_dc_iv.sp")
}

$decks = $deckMap[$Target]
$manifest = @()

Write-Host "HSPICE command: $HspiceCmd"
if ($env:SNPSLMD_LICENSE_FILE) {
    Write-Host "SNPSLMD_LICENSE_FILE: $($env:SNPSLMD_LICENSE_FILE)"
}
else {
    Write-Host "SNPSLMD_LICENSE_FILE is not set."
}

Push-Location $DeckDir
try {
    foreach ($deck in $decks) {
        $deckName = [System.IO.Path]::GetFileNameWithoutExtension($deck)
        $outPrefix = Join-Path $RunDir $deckName

        Write-Host "Running $deck ..."
        & $HspiceCmd -i $deck -o $outPrefix
        if ($LASTEXITCODE -ne 0) {
            $lisPath = "$outPrefix.lis"
            throw "HSPICE failed on $deck with exit code $LASTEXITCODE. Check $lisPath"
        }

        $manifest += [pscustomobject]@{
            deck = $deck
            output_prefix = $outPrefix
        }
    }
}
finally {
    Pop-Location
}

$manifestPath = Join-Path $RunDir "manifest.json"
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host ""
Write-Host "Done. Results are under:"
Write-Host $RunDir
Write-Host "Manifest:"
Write-Host $manifestPath
