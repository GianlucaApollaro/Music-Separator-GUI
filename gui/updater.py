import sys
import os
import urllib.request
import json
import threading
import tempfile
import subprocess
import wx
from gui.version import __version__, get_edition
from gui.i18n_manager import i18n
from gui.config_manager import config

GITHUB_RELEASES_API = "https://api.github.com/repos/GianlucaApollaro/Music-Separator-GUI/releases/latest"

class UpdateDialog(wx.Dialog):
    def __init__(self, parent, version, edition, body, release_url, download_url):
        super().__init__(parent, title=i18n.tr("menu_check_updates"), size=(550, 450))
        self.download_url = download_url
        self.release_url = release_url
        self.version = version
        self.edition = edition

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Message Header
        msg_text = i18n.tr("update_available").format(version=version, edition=edition)
        lbl_msg = wx.StaticText(panel, label=msg_text)
        vbox.Add(lbl_msg, flag=wx.ALL, border=15)

        # Release Notes Text Box
        vbox.Add(wx.StaticText(panel, label="Release Notes:"), flag=wx.LEFT | wx.RIGHT, border=15)
        self.txt_notes = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 200))
        self.txt_notes.SetValue(body)
        vbox.Add(self.txt_notes, proportion=1, flag=wx.EXPAND | wx.ALL, border=15)

        # Button Row
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_install = wx.Button(panel, label=i18n.tr("btn_download_install"))
        self.btn_install.Bind(wx.EVT_BUTTON, self.OnInstall)
        hbox.Add(self.btn_install, flag=wx.RIGHT, border=10)

        self.btn_web = wx.Button(panel, label=i18n.tr("btn_open_release"))
        self.btn_web.Bind(wx.EVT_BUTTON, self.OnOpenWeb)
        hbox.Add(self.btn_web, flag=wx.RIGHT, border=10)

        self.btn_later = wx.Button(panel, label=i18n.tr("btn_later"))
        self.btn_later.Bind(wx.EVT_BUTTON, self.OnLater)
        hbox.Add(self.btn_later)

        vbox.Add(hbox, flag=wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)

        panel.SetSizer(vbox)
        self.Layout()
        self.Centre()

        # If no binary package is found, disable the install button
        if not self.download_url:
            self.btn_install.Disable()
            self.btn_install.SetToolTip(i18n.tr("update_no_asset").format(edition=edition))

    def OnInstall(self, event):
        self.EndModal(wx.ID_YES)

    def OnOpenWeb(self, event):
        import webbrowser
        webbrowser.open(self.release_url)

    def OnLater(self, event):
        self.EndModal(wx.ID_NO)


def check_for_updates(parent, show_up_to_date=True, silent=False):
    """Background check for updates, safe to call from wx event handlers."""
    def _run():
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": f"Music-Separator-GUI/{__version__}"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            tag_name = data.get("tag_name", "").strip()
            remote_version = tag_name.lstrip("vV")
            
            if not remote_version:
                if not silent:
                    wx.CallAfter(wx.MessageBox, i18n.tr("update_err").format(error="Could not read latest version tag."), i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
                return

            # Simple semantic comparison helper
            def parse_version(v_str):
                return [int(x) for x in v_str.split('.') if x.isdigit()]

            curr_parsed = parse_version(__version__)
            rem_parsed = parse_version(remote_version)

            if rem_parsed > curr_parsed:
                # Find the correct download package for current edition
                edition = get_edition()
                download_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    url = asset.get("browser_download_url", "")
                    if edition == "Mac" and "mac" in name.lower() and name.endswith(".zip"):
                        download_url = url
                        break
                    elif edition == "Windows_CPU" and "cpu" in name.lower() and name.endswith(".7z"):
                        download_url = url
                        break
                    elif edition == "Windows_GPU" and "gpu" in name.lower() and name.endswith(".7z"):
                        download_url = url
                        break

                release_url = data.get("html_url", "https://github.com/GianlucaApollaro/Music-Separator-GUI/releases")
                body = data.get("body", "")

                wx.CallAfter(_show_update_dialog, parent, remote_version, edition, body, release_url, download_url)
            else:
                if show_up_to_date and not silent:
                    wx.CallAfter(wx.MessageBox, i18n.tr("update_up_to_date").format(version=__version__), i18n.tr("msg_success_title"), wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            if not silent:
                wx.CallAfter(wx.MessageBox, i18n.tr("update_err").format(error=str(e)), i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)

    threading.Thread(target=_run, daemon=True).start()


def _show_update_dialog(parent, version, edition, body, release_url, download_url):
    dlg = UpdateDialog(parent, version, edition, body, release_url, download_url)
    res = dlg.ShowModal()
    dlg.Destroy()
    if res == wx.ID_YES:
        _start_download(parent, download_url)


def _start_download(parent, download_url):
    # Determine local filename
    parsed_url = urllib.parse.urlparse(download_url)
    filename = os.path.basename(parsed_url.path) or "update.archive"
    temp_dir = tempfile.gettempdir()
    local_path = os.path.join(temp_dir, filename)

    progress = wx.ProgressDialog(
        i18n.tr("menu_check_updates"),
        i18n.tr("update_downloading").format(percent=0),
        maximum=100,
        parent=parent,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
    )

    def _download_thread():
        try:
            req = urllib.request.Request(download_url, headers={"User-Agent": "Music-Separator-GUI-Updater"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_so_far = 0
                chunk_size = 1024 * 64
                
                with open(local_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_so_far += len(chunk)
                        
                        if total_size > 0:
                            percent = int((bytes_so_far / total_size) * 100)
                        else:
                            percent = 50  # Fallback if content-length is not sent
                        
                        # Update progress dialog UI
                        wx.CallAfter(lambda p=percent: progress.Update(p, i18n.tr("update_downloading").format(percent=p)) if progress else None)
                        
                        if progress and progress.WasCancelled():
                            f.close()
                            try:
                                os.remove(local_path)
                            except OSError:
                                pass
                            return

            # Download finished, trigger installation
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(_apply_update_and_exit, parent, local_path)
        except Exception as e:
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(wx.MessageBox, f"{i18n.tr('update_download_err')}\n\n{str(e)}", i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)

    threading.Thread(target=_download_thread, daemon=True).start()


def _apply_update_and_exit(parent, archive_path):
    """Generates the detached launcher updater script, runs it, and terminates the app."""
    pid = os.getpid()
    app_dir = os.path.abspath(os.getcwd())
    temp_dir = tempfile.gettempdir()

    if sys.platform == 'win32':
        # Resolve target executable path
        # If running from PyInstaller executable, sys.executable is the path to the EXE
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.join(app_dir, "Music separator.exe")
        
        if getattr(sys, 'frozen', False):
            # In PyInstaller, the ffmpeg_bin directory is bundled inside sys._MEIPASS or _internal
            original_7z_path = os.path.join(getattr(sys, '_MEIPASS', ''), "ffmpeg_bin", "7za.exe")
            if not os.path.exists(original_7z_path):
                original_7z_path = os.path.join(os.path.dirname(exe_path), "_internal", "ffmpeg_bin", "7za.exe")
        else:
            # Fallback for development/venv setup
            original_7z_path = os.path.join(app_dir, "ffmpeg_bin", "7za.exe")

        # Normalize all paths for batch execution
        exe_path = os.path.normpath(exe_path)
        original_7z_path = os.path.normpath(original_7z_path)
        archive_path = os.path.normpath(archive_path)
        app_dir = os.path.normpath(app_dir)

        update_bat_path = os.path.join(temp_dir, f"update_{pid}.bat")

        # Create batch script that handles both flat archives and archives nested inside a single root folder.
        # It also deletes the old _internal folder (compiled libraries) to ensure clean libraries upgrade.
        bat_content = f"""@echo off
copy /y "{original_7z_path}" "%TEMP%\\7za_temp_updater.exe" >nul
:wait_loop
tasklist /FI "PID eq {pid}" | find "{pid}" >nul
if not errorlevel 1 (
    ping -n 2 127.0.0.1 >nul
    goto wait_loop
)
if exist "%TEMP%\\ms_update_temp" rmdir /s /q "%TEMP%\\ms_update_temp"
"%TEMP%\\7za_temp_updater.exe" x "{archive_path}" -o"%TEMP%\\ms_update_temp" -y
if exist "{app_dir}\\_internal" rmdir /s /q "{app_dir}\\_internal"
set "HAS_DIR="
for /d %%i in ("%TEMP%\\ms_update_temp\\*") do (
    set "HAS_DIR=1"
    xcopy "%%i\\*" "{app_dir}" /s /e /y /h /r >nul
)
if not defined HAS_DIR (
    xcopy "%TEMP%\\ms_update_temp\\*" "{app_dir}" /s /e /y /h /r >nul
)
rmdir /s /q "%TEMP%\\ms_update_temp" >nul 2>&1
start "" "{exe_path}"
del "%TEMP%\\7za_temp_updater.exe" >nul 2>&1
del "%~f0"
"""
        with open(update_bat_path, "w", encoding="ansi") as f:
            f.write(bat_content)

        # Launch detached updater script
        subprocess.Popen([update_bat_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)

    elif sys.platform == 'darwin':
        # Mac updater script
        # On Mac, target app is the .app bundle (usually 3 levels up from macOS executable)
        mac_exe = sys.executable if getattr(sys, 'frozen', False) else ""
        if ".app/Contents/MacOS/" in mac_exe:
            app_bundle_path = mac_exe.split(".app/Contents/MacOS/")[0] + ".app"
            target_dir = os.path.dirname(app_bundle_path)
            app_relaunch_cmd = f'open "{app_bundle_path}"'
        else:
            app_bundle_path = os.path.join(app_dir, "Music separator.app")
            target_dir = app_dir
            app_relaunch_cmd = f'open "{app_bundle_path}"'

        app_bundle_path = os.path.abspath(app_bundle_path)
        target_dir = os.path.abspath(target_dir)

        update_sh_path = os.path.join(temp_dir, f"update_{pid}.sh")

        # Mac updater script unzips to a temporary folder, locates the .app bundle,
        # deletes the old .app bundle completely (to avoid signature / stale file errors),
        # and moves the new app bundle in its place.
        sh_content = f"""#!/bin/bash
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done
rm -rf "/tmp/ms_update_temp"
mkdir -p "/tmp/ms_update_temp"
unzip -o "{archive_path}" -d "/tmp/ms_update_temp"
EXTRACTED_APP=$(find "/tmp/ms_update_temp" -name "*.app" -type d -maxdepth 2 | head -n 1)
if [ -n "$EXTRACTED_APP" ]; then
    rm -rf "{app_bundle_path}"
    mv "$EXTRACTED_APP" "{target_dir}/"
else
    # Fallback to direct unzip if structure is flat
    unzip -o "{archive_path}" -d "{target_dir}"
fi
rm -rf "/tmp/ms_update_temp"
{app_relaunch_cmd}
rm "$0"
"""
        with open(update_sh_path, "w", encoding="utf-8") as f:
            f.write(sh_content)
        
        os.chmod(update_sh_path, 0o755)
        # Launch detached bash script
        subprocess.Popen(["/bin/bash", update_sh_path], start_new_session=True)

    else:
        # Unsupported platforms
        wx.MessageBox("Auto-update is not supported on this platform.", i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
        return

    # Close the application
    parent.Close()
