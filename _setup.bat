@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoLogo -File .\env\dev\setup_env.ps1
powershell -ExecutionPolicy Bypass -NoLogo -File .\env\dev\setup_venv.ps1
endlocal

echo %CMDCMDLINE% | findstr /C:"/c" >nul
if %errorlevel% == 0 (
    cmd /k
)
