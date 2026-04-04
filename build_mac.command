#!/bin/bash
cd "$(dirname "$0")"

VENV_DIR="venv_mac"

echo "==================================================="
echo "   Music Separator - macOS Build Script (.app)     "
echo "==================================================="

if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found! Please run install_mac.command first."
    echo "Press any key to exit..."
    read -n 1 -s
    exit 1
fi

source "$VENV_DIR/bin/activate"

echo "• Installing/Upgrading PyInstaller..."
pip install --upgrade pyinstaller

echo ""
echo "• Building macOS Application Bundle..."
echo "This may take several minutes (Torch is large)..."

# Note: on macOS, the delimiter for --add-data is ":" instead of ";"
pyinstaller --noconsole --onedir --icon=NONE \
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
    --collect-all wx \
    --collect-all audio_separator \
    --add-data "i18n:i18n" \
    --add-data "gui:gui" \
    --name "Music separator" \
    main.py

echo ""
echo "==================================================="
echo "   Build complete! Check the 'dist' folder.        "
echo "==================================================="
echo ""
echo "You will find 'Music separator.app' in the dist folder."
echo "You can move it to your Applications folder."
echo ""
echo "Press any key to close..."
read -n 1 -s
