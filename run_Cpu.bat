@echo off
setlocal

cd /d "%~dp0"
set "VENV_DIR=%~dp0venv_cpu"

if not exist "%VENV_DIR%" (
    echo Virtual environment-CPU not found. Please run install_cpu.bat first.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

"%VENV_DIR%\Scripts\python.exe" "%~dp0main.py"
pause
