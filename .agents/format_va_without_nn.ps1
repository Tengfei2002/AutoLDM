param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Destination
)

$text = [System.IO.File]::ReadAllText($Source)
$text = $text -replace "`r`n", "`n"

# Remove neural-network weight and bias declarations (identifiers beginning with nn).
$text = [regex]::Replace(
    $text,
    '(?im)^[ \t]*real\s+nn[A-Za-z0-9_]*\s*=.*?;\s*(?://[^\n]*)?\n',
    ''
)

# Remove both neural-network evaluation blocks, including normalization inputs and layer outputs.
$text = [regex]::Replace(
    $text,
    '(?is)^[ \t]*//\s*\*+\s*calculation starts NN1.*?^[ \t]*//\s*\*+\s*calculation ends NN5.*?\n',
    ''
)
# Remove neural-network output identifiers from physical equations using neutral factors.
$text = [regex]::Replace($text, '\b(?:sce|clm|qua|mob|cv|gidl)_output\d+\b', '1.0')

# The activation functions are used only by the removed neural-network layers.
$text = [regex]::Replace(
    $text,
    '(?is)^[ \t]*//\s*\*+\s*Activation function (?:tansig|logsig).*?^[ \t]*endfunction\s*\n',
    ''
)

$skipNetwork = $false
$lines = foreach ($line in ($text -split "`n")) {
    if ($line -match 'input normalizations') {
        $skipNetwork = $true
        continue
    }
    if ($skipNetwork) {
        if ($line -match 'calculation ends NN5') { $skipNetwork = $false }
        continue
    }
    $line = $line -replace "`t", '    '
    $line = $line.TrimEnd()

    # Remove neural-network inputs, intermediate neurons, and output variables.
    if ($line -match '^\s*real\b.*\b(?:tgaa_nor|w_nor|l_nor|neuron[A-Za-z0-9_]*|[A-Za-z0-9_]*_output[A-Za-z0-9_]*)\b') {
        continue
    }

    # Delete only the known meaningless hash-and-digit annotation, preserving code.
    $line = [regex]::Replace($line, '\s*//\s*#+\d+\s*$', '')
    if ($line -match '^\s*//\s*NN\d+') { continue }

    # Convert decorative section banners to concise, readable headings.
    if ($line -match '^\s*//[/\*]+\s*$' -or $line -match '^\s*/\*{3,}/\s*$') {
        continue
    }
    $line = [regex]::Replace(
        $line,
        '^\s*//\s*\*+\s*(.*?)\s*\*+//\s*$',
        '// $1'
    )

    if ($line -match '^\s*//\s*(?:input weight matrix|nnwa_b_c|a means the number of hidden layers|b means the b th neurons of the a layer|c measns the weight between the b th neurons of the a layer and the c of the previous layer|NN Model \d+:.*|(?:1st|2nd|Output) (?:hidden layer |layer )?(?:weight|threshold).*)\s*$') {
        continue
    }

    # NN parameter-matrix comments have no remaining content after the declarations are removed.
    if ($line -match '^\s*//.*(?:input weight matrix|nnwa_b_c|number of hidden layers|th neurons|weight between).*//\s*$') {
        continue
    }
    if ($line -match '^\s*//\s*\*+\s*NN Model \d+.*//\s*$') {
        continue
    }
    if ($line -match '^\s*//\s*\*+\s*(?:1st|2nd|Output) (?:hidden layer |layer )?(?:weight|threshold).*//\s*$') {
        continue
    }

    # Standardize top-level scalar declarations while keeping expressions unchanged.
    $line = [regex]::Replace(
        $line,
        '^(\s*)(parameter\s+real|real)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*;\s*$',
        '$1$2 $3 = $4;'
    )

    # Keep module-level declarations and structural comments at one indentation level.
    if ($line -match '^\s*(?:inout|electrical|parameter\s+real|real)\b') {
        $line = '    ' + $line.TrimStart()
    }
    $line
}

# Avoid excessive vertical whitespace and use CRLF, the repository's existing convention.
$result = [System.Collections.Generic.List[string]]::new()
$previousBlank = $false
foreach ($line in $lines) {
    $blank = [string]::IsNullOrWhiteSpace($line)
    if ($blank -and $previousBlank) { continue }
    $result.Add($line)
    $previousBlank = $blank
}

[System.IO.File]::WriteAllText(
    $Destination,
    (($result -join "`r`n").TrimEnd() + "`r`n"),
    [System.Text.UTF8Encoding]::new($false)
)
