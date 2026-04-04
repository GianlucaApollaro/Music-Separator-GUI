#!/bin/bash
cd "$(dirname "$0")"

VENV_DIR="venv_mac"

echo "====================================="
echo "   Music Separator macOS Installer   "
echo "====================================="

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "• Creating virtual environment..."
    # Prova con python3.12, altrimenti ripiega su python3
    python3.12 -m venv "$VENV_DIR" 2>/dev/null || python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo "Error: Python 3 not found on your system."
        echo "Please install Python 3 (from python.org or via Homebrew)."
        exit 1
    fi
else
    echo "• Virtual environment already exists."
fi

source "$VENV_DIR/bin/activate"

echo "• Upgrading pip..."
pip install --upgrade pip

echo "• Installing PyTorch optimized for Apple Silicon (MPS)..."
pip install torch torchvision torchaudio

echo "• Installing application requirements..."
pip install --no-cache-dir -r requirements.txt

echo "• Installing PyInstaller (optional for builds)..."
pip install pyinstaller

echo ""
echo "====================================="
echo "       Installation complete!        "
echo "====================================="
echo ""
echo "IMPORTANT: If you haven't already, please ensure FFmpeg is installed."
echo "On Mac, the easiest way is to install Homebrew and run:"
echo "    brew install ffmpeg"
echo ""
echo "Press any button or close the terminal to exit..."
read -n 1 -s
