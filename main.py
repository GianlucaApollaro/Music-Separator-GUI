import multiprocessing

if __name__ == '__main__':
    # PyInstaller workers and resource trackers re-enter this executable.
    # Dispatch them before GUI/audio imports or CLI argument handling, on all
    # platforms (including macOS), so they do not launch another app instance.
    multiprocessing.freeze_support()

import sys
import os
import subprocess

# If arguments are passed on Windows with a GUI-built executable, attach to parent console
if sys.platform == 'win32' and len(sys.argv) > 1:
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
            sys.stderr = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
    except Exception:
        pass

if sys.stdout is None or sys.stderr is None:
    # When running with --noconsole, PyInstaller sets sys.stdout and sys.stderr to None.
    # However, some libraries (like audio-separator/FFmpeg) attempt to get the file
    # descriptor (fileno) of stdout/stderr and will crash with Errno 22 Invalid argument
    # or OSError if they get a bad descriptor.
    # To fix this, we map them to open os.devnull AND ensure they share that fileno.
    devnull = open(os.devnull, 'w')
    if sys.stdout is None:
        sys.stdout = devnull
    if sys.stderr is None:
        sys.stderr = devnull

from gui.utils import get_base_path
base_dir = get_base_path()

# Determine bundled ffmpeg directory based on platform
ffmpeg_bundled_dir = 'ffmpeg_Mac_bin' if sys.platform == 'darwin' else 'ffmpeg_bin'
ffmpeg_path = os.path.join(base_dir, ffmpeg_bundled_dir)

if os.path.exists(ffmpeg_path):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

# Special PATH handling for macOS to find Homebrew or local FFmpeg as fallbacks
if sys.platform == 'darwin':
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
    for path in extra_paths:
        if path not in os.environ["PATH"]:
            os.environ["PATH"] = os.environ["PATH"] + os.pathsep + path

# Prevent subprocesses (like FFmpeg) from opening new console windows
if os.name == 'nt':
    _original_popen = subprocess.Popen
    class NoWindowPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            super().__init__(*args, **kwargs)
    subprocess.Popen = NoWindowPopen

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Force PyInstaller to include these hidden dependencies
try:
    import neuralop
    import einops
except ImportError:
    pass

def main():
    if len(sys.argv) > 1:
        from gui.cli import run_cli
        sys.exit(run_cli(sys.argv[1:]))

    import wx
    from gui.main_window import MainWindow

    app = wx.App(False)
    frame = MainWindow(None, title="Music separator")
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()
