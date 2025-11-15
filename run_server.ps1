# Django Development Server Startup Script
# This script activates the virtual environment and runs the Django server

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Navigate to the virtual environment directory
$venvPath = Join-Path $scriptDir "my_final\my_final\my_final"
$projectPath = Join-Path $venvPath "our_project"

# Check if virtual environment exists
if (-Not (Test-Path (Join-Path $venvPath "Scripts\Activate.ps1"))) {
    Write-Host "Error: Virtual environment not found at $venvPath" -ForegroundColor Red
    exit 1
}

# Check if project exists
if (-Not (Test-Path (Join-Path $projectPath "manage.py"))) {
    Write-Host "Error: Django project not found at $projectPath" -ForegroundColor Red
    exit 1
}

# Change to project directory
Set-Location $projectPath

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
} else {
    Write-Host "Error: Activation script not found at $activateScript" -ForegroundColor Red
    exit 1
}

# Run the Django server
Write-Host "Starting Django development server..." -ForegroundColor Green
Write-Host "Server will be available at http://127.0.0.1:8000/" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python manage.py runserver

