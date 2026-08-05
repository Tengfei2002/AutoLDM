param(
    [string]$InstallDir = "",
    [string]$LicenseServer = "27000@LAPTOP-K9QP6UAM"
)

$ErrorActionPreference = "Stop"

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

if (-not (Test-Path -LiteralPath $InstallDir)) {
    throw "HSPICE install directory does not exist: $InstallDir"
}

$win64Dir = Join-Path $InstallDir "WIN64"
$binDir = Join-Path $InstallDir "BIN"

[Environment]::SetEnvironmentVariable("SNPSLMD_LICENSE_FILE", $LicenseServer, "User")
[Environment]::SetEnvironmentVariable("LM_LICENSE_FILE", $LicenseServer, "User")
[Environment]::SetEnvironmentVariable("installdir_O-2018.09", $InstallDir, "User")
[Environment]::SetEnvironmentVariable("installdir_P-2019.06-SP1-1", $InstallDir, "User")

$currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathParts = @()
if (-not [string]::IsNullOrWhiteSpace($currentUserPath)) {
    $pathParts = $currentUserPath -split ";"
}

foreach ($pathToAdd in @($win64Dir, $binDir)) {
    if (($pathParts | Where-Object { $_ -ieq $pathToAdd }).Count -eq 0) {
        $pathParts += $pathToAdd
    }
}

[Environment]::SetEnvironmentVariable("Path", ($pathParts -join ";"), "User")

Set-Item -Path Env:SNPSLMD_LICENSE_FILE -Value $LicenseServer
Set-Item -Path Env:LM_LICENSE_FILE -Value $LicenseServer
Set-Item -Path Env:'installdir_O-2018.09' -Value $InstallDir
Set-Item -Path Env:'installdir_P-2019.06-SP1-1' -Value $InstallDir
$env:Path = ([Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User"))

Write-Host "Configured user environment:"
Write-Host "  SNPSLMD_LICENSE_FILE=$LicenseServer"
Write-Host "  LM_LICENSE_FILE=$LicenseServer"
Write-Host "  installdir_O-2018.09=$InstallDir"
Write-Host "  installdir_P-2019.06-SP1-1=$InstallDir"
Write-Host "  Added to user Path:"
Write-Host "    $win64Dir"
Write-Host "    $binDir"
Write-Host ""
Write-Host "Open a new terminal for persistent environment changes to appear automatically."
