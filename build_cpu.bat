@echo off
cd /d "%~dp0"
echo ===================================================
echo Music separator - Build Script - CPU ONLY
echo ===================================================

if not exist venv_cpu (
    echo Virtual environment-CPU not found! Please run install_cpu.bat first.
    pause
    exit /b
)

set "VENV_DIR=%~dp0venv_cpu"
call "%VENV_DIR%\Scripts\activate"

echo Installing/Upgrading PyInstaller...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pyinstaller

echo.
echo Building CPU-only executable...
echo This should be much faster than the GPU build (Torch ~250MB)...

"%VENV_DIR%\Scripts\python.exe" -m PyInstaller --noconsole --onedir --icon=NONE ^
    --hidden-import=torch --hidden-import=torchvision --hidden-import=torchaudio ^
    --hidden-import=audio_separator --hidden-import=wx --hidden-import=onnxruntime ^
    --hidden-import=wx._core --hidden-import=wx._windows --hidden-import=wx.lib.agw ^
    --hidden-import=wx.lib.pubsub --hidden-import=wx.lib.scrolledpanel ^
    --hidden-import=neuralop --hidden-import=neuralop.models --hidden-import=neuralop.models.fno --hidden-import=einops ^
    --collect-all wx --collect-all audio_separator --collect-all neuralop ^
    --add-data "i18n;i18n" --add-data "ffmpeg_bin;ffmpeg_bin" ^
    --name "Music separator CPU" ^
    main.py

echo.
echo Check "dist\Music separator CPU" folder for your executable.
echo Please manually copy the "models" folder to the same directory as the .exe if you want to ship pre-downloaded models.
pause
