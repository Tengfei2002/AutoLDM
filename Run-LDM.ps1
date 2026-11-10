param([Parameter(ValueFromRemainingArguments=$true)][string[]]$LdmArguments)
$ErrorActionPreference = 'Stop'
$candidates = @(
    (Join-Path $PSScriptRoot '.venv/Scripts/python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Python/bin/python3.14.exe'),
    (Join-Path $env:USERPROFILE 'AppData/Local/Python/bin/python3.14.exe')
)
$python = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $found = & uv python find --offline 2>$null
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $found)) { $python = $found }
    }
}
if (-not $python) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*WindowsApps*') { $python = $command.Source }
}
if (-not $python) { throw 'Install Python 3.10+ or create .venv. The WindowsApps alias is not a Python installation.' }
& $python -B (Join-Path $PSScriptRoot 'ldm.py') @LdmArguments
exit $LASTEXITCODE
