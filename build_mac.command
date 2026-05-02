#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")" || exit 1

VENV_DIR="venv_mac"
APP_NAME="Music separator"
APP_PATH="dist/${APP_NAME}.app"
EXECUTABLE_PATH="$APP_PATH/Contents/MacOS/${APP_NAME}"

printf '%s\n' "==================================================="
printf '%s\n' "   Music Separator - macOS Build Script (.app)     "
printf '%s\n' "==================================================="

if [ ! -d "$VENV_DIR" ]; then
    printf '%s\n' "Virtual environment not found! Please run install_mac.command first."
    printf '%s\n' "Press any key to exit..."
    read -n 1 -s
    exit 1
fi

source "$VENV_DIR/bin/activate"

printf '%s\n' "• Installing/Upgrading PyInstaller..."
python -m pip install --upgrade pyinstaller

printf '%s\n' "• Cleaning previous builds..."
rm -rf build dist "${APP_NAME}.spec"

printf '\n'
printf '%s\n' "• Building macOS Application Bundle..."
printf '%s\n' "This may take several minutes (Torch is large)..."

pyinstaller --windowed \
    --target-arch arm64 \
    --osx-bundle-identifier "it.gianluca.musicseparator" \
    --hidden-import=torch \
    --hidden-import=torchvision \
    --hidden-import=torchaudio \
    --hidden-import=audio_separator \
    --hidden-import=wx \
    --hidden-import=onnxruntime \
    --hidden-import=wx._core \
    --hidden-import=wx._windows \
    --hidden-import=wx.lib.agw \
    --hidden-import=wx.lib.pubsub \
    --hidden-import=wx.lib.scrolledpanel \
    --hidden-import=neuralop \
    --hidden-import=neuralop.models \
    --hidden-import=neuralop.models.fno \
    --hidden-import=einops \
    --collect-all wx \
    --collect-all audio_separator \
    --collect-all neuralop \
    --add-data "i18n:i18n" \
    --add-data "gui:gui" \
    --add-data "ffmpeg_Mac_bin:ffmpeg_Mac_bin" \
    --name "$APP_NAME" \
    main.py

if [ -f "$EXECUTABLE_PATH" ]; then
    chmod +x "$EXECUTABLE_PATH"
fi

printf '\n'
printf '%s\n' "==================================================="
printf '%s\n' "   Build complete! Check the 'dist' folder.        "
printf '%s\n' "==================================================="
printf '\n'
printf '%s\n' "You will find 'Music separator.app' in the dist folder."
printf '%s\n' "You can move it to your Applications folder."
printf '%s\n' "Press any key to close..."
read -n 1 -s
