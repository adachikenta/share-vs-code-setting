$venvpath = ".\venv"
Write-Host "Starting coverage report generation..." -ForegroundColor Cyan
# Check if .coverage file exists
if (-not (Test-Path -Path ".coverage")) {
    Write-Host "Error: .coverage file not found. Please run tests to generate coverage data." -ForegroundColor Red
    exit 1
}
Write-Host "`n.coverage file found. Generating coverage report." -ForegroundColor Green
# Activate application development virtual environment
$envActivatePath = "$venvpath\Scripts\Activate.ps1"
if (Test-Path -Path $envActivatePath) {
    try {
        Write-Host "`nActivating virtual environment..." -ForegroundColor Cyan
        & $envActivatePath
    } catch {
        Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Error: Virtual environment not found. Please run app_devenv_setup.bat to set up the environment." -ForegroundColor Red
    exit 1
}
# Display coverage summary
Write-Host "`n===== COVERAGE SUMMARY =====" -ForegroundColor Cyan
try {
    & python -m coverage report
} catch {
    Write-Host "Error: An error occurred while generating the coverage report." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
# Display detailed coverage report (including missing lines)
Write-Host "`n===== DETAILED COVERAGE REPORT =====" -ForegroundColor Cyan
try {
    & python -m coverage report -m
} catch {
    Write-Host "Error: An error occurred while generating the detailed coverage report." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
# Generate coverage report
Write-Host "`n===== GENERATING coverage REPORT =====" -ForegroundColor Cyan
try {
    & python -m coverage html -d __cov__/internal --title "Internal Test Coverage Report"
} catch {
    Write-Host "Error: An error occurred while generating the coverage report." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
# Display coverage report location
$covReportPath = Join-Path -Path (Get-Location) -ChildPath "__cov__\internal\index.html"
if (Test-Path -Path $covReportPath) {
    Write-Host "`ncoverage report successfully generated:" -ForegroundColor Green
    # move .coverage in to __cov__/internal
    Move-Item -Path ".coverage" -Destination (Join-Path -Path (Get-Location) -ChildPath "__cov__\internal\.coverage") -Force
    Write-Host $covReportPath -ForegroundColor Yellow
    # Ask if user wants to open the report
    #$openReport = Read-Host "Would you like to open the coverage report in your browser? (y/n)"
    #if ($openReport -eq "y") {
        Start-Process $covReportPath
    #}
} else {
    Write-Host "`nWarning: coverage report file not found." -ForegroundColor Yellow
}
# Deactivate virtual environment
deactivate
Write-Host "`nCoverage report generation completed." -ForegroundColor Green
