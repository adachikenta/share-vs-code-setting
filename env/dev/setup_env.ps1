$ErrorActionPreference = "Stop"
$venvPath = ".\venv"
$pythonVersion = "python312"

function Install-ScoopPackage {
    param(
        [string]$PackageName,
        [string]$ExecutablePath,
        [int]$MaxRetries = 2
    )

    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        try {
            # Check if already installed and working
            if (Test-Path $ExecutablePath) {
                Write-Host "$PackageName is already installed." -ForegroundColor Green
                return $true
            }

            # Check if package exists but is broken
            $scoopList = scoop list 2>&1 | Out-String
            if ($scoopList -match $PackageName) {
                Write-Host "$PackageName is installed but not working. Reinstalling..." -ForegroundColor Yellow
                scoop uninstall $PackageName 2>&1 | Out-Null
                Start-Sleep -Seconds 2
            }

            # Install the package
            Write-Host "$PackageName is not installed. Installing $PackageName..." -ForegroundColor Yellow
            $output = scoop install $PackageName 2>&1

            # Wait for installation to complete
            Start-Sleep -Seconds 3

            # Verify installation
            if (Test-Path $ExecutablePath) {
                Write-Host "$PackageName installed successfully." -ForegroundColor Green
                return $true
            } else {
                $errorMsg = "$PackageName installation completed but executable not found at $ExecutablePath"
                if ($output) {
                    $errorMsg += "`nInstallation output: $output"
                }
                throw $errorMsg
            }
        }
        catch {
            $attempt++
            Write-Host "Attempt $attempt failed: $_" -ForegroundColor Red
            if ($attempt -lt $MaxRetries) {
                Write-Host "Retrying..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            } else {
                Write-Host "Failed to install $PackageName after $MaxRetries attempts." -ForegroundColor Red
                return $false
            }
        }
    }
    return $false
}

# check if scoop is installed
if (Get-Command scoop -ErrorAction SilentlyContinue) {
    Write-Host "scoop is already installed." -ForegroundColor Green
} else {
    # install scoop
    Write-Host "scoop is not installed. Installing scoop..." -ForegroundColor Yellow
    try {
        Invoke-Expression "& {$(Invoke-RestMethod get.scoop.sh)} -RunAsAdmin"
        Write-Host "scoop installed successfully." -ForegroundColor Green
    }
    catch {
        Write-Host "Failed to install scoop: $_" -ForegroundColor Red
        exit 1
    }
}

# check if git of scoop is installed
$scoopgit = "$env:USERPROFILE\scoop\apps\git\current\bin\git.exe"
$gitInstalled = Install-ScoopPackage -PackageName "git" -ExecutablePath $scoopgit
if (-not $gitInstalled) {
    Write-Host "Failed to install git. Exiting..." -ForegroundColor Red
    exit 1
}

# check sslbackend of git
try {
    $gitConfig = & $scoopgit config --global -l 2>&1
    if ($gitConfig -match "http.sslbackend=schannel") {
        Write-Host "git sslbackend is already set to schannel." -ForegroundColor Green
    } else {
        Write-Host "Setting git sslbackend to schannel..." -ForegroundColor Yellow
        & $scoopgit config --global http.sslbackend schannel
        Write-Host "git sslbackend set to schannel successfully." -ForegroundColor Green
    }
}
catch {
    Write-Host "Warning: Could not configure git sslbackend: $_" -ForegroundColor Yellow
}

# check versions bucket
try {
    $buckets = scoop bucket list 2>&1 | Out-String
    if ($buckets -match "versions") {
        Write-Host "versions bucket is already added." -ForegroundColor Green
    } else {
        Write-Host "Adding versions bucket..." -ForegroundColor Yellow
        scoop bucket add versions
        Write-Host "versions bucket added successfully." -ForegroundColor Green
    }
}
catch {
    Write-Host "Warning: Could not add versions bucket: $_" -ForegroundColor Yellow
}

# check if python of scoop is installed
$scooppython = "$env:USERPROFILE\scoop\apps\$pythonVersion\current\python.exe"
$pythonInstalled = Install-ScoopPackage -PackageName $pythonVersion -ExecutablePath $scooppython

if (-not $pythonInstalled) {
    Write-Host "Failed to install Python. Exiting..." -ForegroundColor Red
    exit 1
}

# Verify Python is working
try {
    $pythonVersionOutput = & $scooppython --version 2>&1
    Write-Host "Python version: $pythonVersionOutput" -ForegroundColor Green
}
catch {
    Write-Host "Python executable exists but is not working properly: $_" -ForegroundColor Red
    exit 1
}

# create a Python virtual environment in the 'venv' directory
if (Test-Path -Path $venvPath) {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
} else {
    Write-Host "Creating virtual environment ..." -ForegroundColor Yellow
    try {
        & $scooppython -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw "venv creation failed with exit code $LASTEXITCODE"
        }
        # Verify venv was created
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        if (-not (Test-Path $activateScript)) {
            throw "Virtual environment created but activation script not found"
        }
        Write-Host "Virtual environment created successfully." -ForegroundColor Green
    }
    catch {
        Write-Host "Failed to create virtual environment: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Virtual environment is located at $venvPath" -ForegroundColor Green
Write-Host "Setup completed successfully." -ForegroundColor Green
