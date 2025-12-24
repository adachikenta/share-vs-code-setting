$ErrorActionPreference = "Stop"
$venvPath = ".\venv"
if (Test-Path $venvPath) {
    $absoluteVenvPath = (Resolve-Path -Path $venvPath -ErrorAction SilentlyContinue).Path
    # check if python exe in the virtual environment is running
    $pythonExe = Join-Path -Path $absoluteVenvPath -ChildPath "Scripts\python.exe"
    if (Get-Process | Where-Object { $_.Path -eq $pythonExe }) {
        Write-Host "killing python process at $pythonExe" -ForegroundColor Yellow
        Get-Process | Where-Object { $_.Path -eq $pythonExe } | ForEach-Object {
            try {
                Stop-Process -Id $_.Id -Force -ErrorAction Stop
                Write-Host "Python process with ID $($_.Id) stopped successfully." -ForegroundColor Green
            } catch {
                Write-Host "Failed to stop Python process with ID $($_.Id): $_" -ForegroundColor Red
                exit
            }
        }
    } else {
        Write-Host "Not found process $pythonExe" -ForegroundColor Green
    }
} else {
    Write-Host "Virtual environment not found at $venvPath" -ForegroundColor Green
}
# Check if git repository exists
$gitPath = ".\.git"
if (-not (Test-Path $gitPath)) {
    Write-Host "Git repository not found. Initializing git repository with 'develop' branch..." -ForegroundColor Yellow
    try {
        # Initialize git repository
        git init
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Git repository initialized successfully." -ForegroundColor Green

            # Create and checkout develop branch
            git checkout -b develop
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Created and switched to 'develop' branch." -ForegroundColor Green
            } else {
                Write-Host "Warning: Failed to create 'develop' branch." -ForegroundColor Yellow
            }
        } else {
            Write-Host "Warning: Failed to initialize git repository." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Error initializing git repository: $_" -ForegroundColor Red
    }
}

$gitignorePath = ".\.gitignore"
if (Test-Path $gitignorePath) {
    # Check if in a git repository
    git rev-parse --git-dir 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        try {
            Write-Host "Removing files ignored by .gitignore..." -ForegroundColor Yellow
            git clean -fdX
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Ignored files removed successfully." -ForegroundColor Green
            } else {
                Write-Host "Warning: git clean had issues." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "Failed to clean git ignored files: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "Not in a git repository. Skipping git clean." -ForegroundColor Yellow
    }
} else {
    Write-Host ".gitignore file not found at $gitignorePath" -ForegroundColor Yellow
    Write-Host "Skipping git clean operation." -ForegroundColor Yellow
}
