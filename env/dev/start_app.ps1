$ErrorActionPreference = "Stop"

$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    exit 1
}

# Check if Python script path is provided as argument
if ($args.Count -eq 0) {
    Write-Host "Error: No Python script path provided." -ForegroundColor Red
    Write-Host "Usage: .\start_app.ps1 <python_script_path>" -ForegroundColor Yellow
    exit 1
}

$pythonScript = $args[0]

# Verify the Python script exists
if (-not (Test-Path $pythonScript)) {
    Write-Host "Error: Python script not found: $pythonScript" -ForegroundColor Red
    exit 1
}

# Run the application
try {
    Write-Host "Starting Python script: $pythonScript" -ForegroundColor Green
    python $pythonScript
    $appResult = $LASTEXITCODE
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    $appResult = 1
} finally {
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }

    if ($appResult -eq 0) {
        Write-Host "Python script completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Python script exited with errors. Exit code: $appResult" -ForegroundColor Red
    }
}
