@echo off
cd /d "%~dp0"
echo ===================================================
echo Music separator - Build Script
echo ===================================================

if not exist venv (
    echo Virtual environment not found! Please run install.bat first.
    pause
    exit /b
)

set "VENV_DIR=%~dp0venv"
call "%VENV_DIR%\Scripts\activate"

echo Installing/Upgrading PyInstaller...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pyinstaller

echo.
echo Building executable...
echo This may take 5-15 minutes (Torch ~2GB)...

"%VENV_DIR%\Scripts\python.exe" -m PyInstaller --noconsole --onedir --icon=NONE ^
    --hidden-import=torch --hidden-import=torchvision --hidden-import=torchaudio ^
    --hidden-import=audio_separator --hidden-import=wx --hidden-import=onnxruntime ^
    --hidden-import=wx._core --hidden-import=wx._windows --hidden-import=wx.lib.agw ^
    --hidden-import=wx.lib.pubsub --hidden-import=wx.lib.scrolledpanel ^
    --collect-all wx --collect-all audio_separator ^
    --add-data "i18n;i18n" --add-data "ffmpeg_bin;ffmpeg_bin" ^
    --name "Music separator" ^
    main.py

echo.
echo Check "dist" folder for your executable.
echo Please manually copy the "models" folder to the same directory as the .exe if you want to ship pre-downloaded models.
pause
