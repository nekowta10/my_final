<#
PowerShell helper to run the Django manage.py using the venv python when present.
Usage: .\run.ps1 runserver   or  .\run.ps1 test
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    $RemainingArgs
)

# Try to use the repository venv python if it exists
$venvPython = Join-Path $PSScriptRoot 'Scripts\python.exe'

try {
    if (Test-Path $venvPython) {
        & $venvPython (Join-Path $PSScriptRoot 'our_project\manage.py') @RemainingArgs
    }
    else {
        # Fall back to whatever 'python' is on PATH
        & python (Join-Path $PSScriptRoot 'our_project\manage.py') @RemainingArgs
    }
}
catch {
    Write-Error "Failed to run manage.py: $_"
    exit 1
}
