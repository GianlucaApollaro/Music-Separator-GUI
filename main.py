import sys
import os
import subprocess

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

# Inject bundled ffmpeg_bin into system PATH so libraries can find it
import sys
if getattr(sys, 'frozen', False):
    # If running as PyInstaller bundle
    base_dir = sys._MEIPASS
else:
    # If running as normal Python script
    base_dir = os.path.dirname(os.path.abspath(__file__))

ffmpeg_path = os.path.join(base_dir, 'ffmpeg_bin')
if os.path.exists(ffmpeg_path):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

# Special PATH handling for macOS to find Homebrew or local FFmpeg
if sys.platform == 'darwin':
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
    for path in extra_paths:
        if path not in os.environ["PATH"]:
            os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]

# Prevent subprocesses (like FFmpeg) from opening new console windows
if os.name == 'nt':
    _original_popen = subprocess.Popen
    class NoWindowPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            super().__init__(*args, **kwargs)
    subprocess.Popen = NoWindowPopen

import wx
from gui.main_window import MainWindow

def main():
    app = wx.App(False)
    frame = MainWindow(None, title="Music separator")
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()
