@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoLogo -File .\env\dev\clean.ps1

endlocal

echo %CMDCMDLINE% | findstr /C:"/c" >nul
if %errorlevel% == 0 (
    cmd /k
)
