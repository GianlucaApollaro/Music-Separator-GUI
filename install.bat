@echo off
setlocal

cd /d "%~dp0"
set "VENV_DIR=%~dp0venv"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Creating virtual environment...
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

echo Installing PyTorch Nightly (CUDA 12.8)...
"%VENV_DIR%\Scripts\python.exe" -m pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

echo Installing other requirements...
"%VENV_DIR%\Scripts\python.exe" -m pip install --no-cache-dir -r "%~dp0requirements.txt"

echo Installing PyInstaller...
"%VENV_DIR%\Scripts\python.exe" -m pip install pyinstaller

echo.
echo Installation complete.
pause
