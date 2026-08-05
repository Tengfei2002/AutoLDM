param(
    [string]$InstallDir = "",
    [string]$PackageDir = "D:\Hspice\hspice for win\HSPICE2018",
    [string]$LicenseServer = "27000@LAPTOP-K9QP6UAM",
    [string]$Lmutil = "C:\synopsys\SCL\2018.06-SP1\win32\bin\lmutil.exe",
    [switch]$FullLicenseStatus
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

Write-Host "Checking HSPICE installation..."
Write-Host "InstallDir: $InstallDir"
Write-Host "PackageDir: $PackageDir"
Write-Host ""

$requiredPaths = @(
    $InstallDir,
    (Join-Path $InstallDir "BIN\hspice.bat"),
    (Join-Path $InstallDir "WIN64\hspice.com"),
    (Join-Path $InstallDir "WIN64\hspice.exe"),
    (Join-Path $InstallDir "WIN64\hspui.exe"),
    (Join-Path $InstallDir "BIN\awaves.exe"),
    (Join-Path $InstallDir "include"),
    (Join-Path $InstallDir "parts"),
    (Join-Path $InstallDir "Hspice.ini"),
    $Lmutil,
    (Join-Path $PackageDir "hspice_vO-2018.09-VAL-20180412_win.exe"),
    (Join-Path $PackageDir "README_win.txt")
)

foreach ($path in $requiredPaths) {
    if (Test-Path -LiteralPath $path) {
        Write-Host "[OK]      $path"
    }
    else {
        Write-Host "[MISSING] $path"
    }
}

Write-Host ""
Write-Host "Checking license port..."
$serverParts = $LicenseServer -split "@", 2
if ($serverParts.Count -eq 2) {
    $port = [int]$serverParts[0]
    $hostName = $serverParts[1]
    Test-NetConnection $hostName -Port $port
}
else {
    Write-Host "LicenseServer should look like 27080@host."
}

if (Test-Path -LiteralPath $Lmutil) {
    Write-Host ""
    Write-Host "Checking FlexNet status with lmutil..."
    $lmstatOutput = & $Lmutil lmstat -a -c $LicenseServer
    if ($FullLicenseStatus) {
        $lmstatOutput
    }
    else {
        $patterns = @(
            "License server status",
            "license server UP",
            "Vendor daemon status",
            "snpslmd:",
            "Users of hspice",
            "Users of hspicewin"
        )
        $lmstatOutput | Where-Object {
            $line = $_
            ($patterns | Where-Object { $line -match $_ }).Count -gt 0
        }
        Write-Host ""
        Write-Host "Tip: add -FullLicenseStatus to print the complete lmstat feature list."
    }
}
