import sys
import os

__version__ = "1.6"

def get_edition() -> str:
    """Return 'Mac', 'Windows_CPU', 'Windows_GPU', or 'Unknown' based on platform and executable name."""
    if sys.platform == 'darwin':
        return "Mac"
    elif sys.platform == 'win32':
        # PyInstaller sets sys.executable to the path of the built EXE.
        # If running in venv/development, fallback to sys.argv[0].
        exe_path = sys.executable if getattr(sys, 'frozen', False) else (sys.argv[0] or "")
        exe_name = os.path.basename(exe_path).lower()
        if "cpu" in exe_name:
            return "Windows_CPU"
        else:
            return "Windows_GPU"
    return "Unknown"
