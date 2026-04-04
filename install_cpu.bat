@echo off
setlocal

cd /d "%~dp0"
set "VENV_DIR=%~dp0venv_cpu"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Creating virtual environment for CPU...
    py -3.12 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Error: Python 3.12 not found. Install it from python.org.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

call "%VENV_DIR%\Scripts\activate.bat"

echo Upgrading pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip

echo Installing PyTorch CPU Only...
"%VENV_DIR%\Scripts\python.exe" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo Installing other requirements...
"%VENV_DIR%\Scripts\python.exe" -m pip install --no-cache-dir -r "%~dp0requirements.txt"

echo Installing PyInstaller...
"%VENV_DIR%\Scripts\python.exe" -m pip install pyinstaller

echo.
echo Installation for CPU complete.
pause
