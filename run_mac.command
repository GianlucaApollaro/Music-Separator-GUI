#!/bin/bash
cd "$(dirname "$0")"

VENV_DIR="venv_mac"

if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Please run install_mac.sh first."
    echo "Press any key to exit..."
    read -n 1 -s
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Add standard Homebrew paths just in case FFmpeg is installed there
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

python main.py

echo "Program exited. Press any key to close the terminal..."
read -n 1 -s
