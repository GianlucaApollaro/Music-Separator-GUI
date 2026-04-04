@echo off
setlocal

cd /d "%~dp0"
set "VENV_DIR=%~dp0venv"

if not exist "%VENV_DIR%" (
    echo Virtual environment not found. Please run install.bat first.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

"%VENV_DIR%\Scripts\python.exe" "%~dp0main.py"
pause
