@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoLogo -File .\env\dev\start_app.ps1 ".\vscode\setting.py"
endlocal

echo %CMDCMDLINE% | findstr /C:"/c" >nul
if %errorlevel% == 0 (
    cmd /k
)
