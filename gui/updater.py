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
        cancelled = [False]
        try:
            req = urllib.request.Request(download_url, headers={"User-Agent": "Music-Separator-GUI-Updater"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_so_far = 0
                chunk_size = 1024 * 64

                # wx APIs must run on the UI thread: progress.Update and
                # WasCancelled() are both called from here via CallAfter, and the
                # result is propagated back to the worker thread with a shared flag.
                def _update_progress(p):
                    if progress:
                        progress.Update(p, i18n.tr("update_downloading").format(percent=p))
                        if progress.WasCancelled():
                            cancelled[0] = True

                with open(local_path, "wb") as f:
                    while not cancelled[0]:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_so_far += len(chunk)

                        if total_size > 0:
                            percent = int((bytes_so_far / total_size) * 100)
                        else:
                            percent = 50  # Fallback if content-length is not sent

                        wx.CallAfter(_update_progress, min(percent, 100))

            if cancelled[0]:
                try:
                    os.remove(local_path)
                except OSError:
                    pass
                wx.CallAfter(progress.Destroy)
                return

            # A dropped connection ends the read loop without raising. Installing a
            # truncated archive would brick the app, so refuse to proceed.
            if total_size > 0 and bytes_so_far != total_size:
                raise IOError(
                    f"Incomplete download: {bytes_so_far}/{total_size} bytes"
                )

            # Download finished, trigger installation
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(_apply_update_and_exit, parent, local_path)
        except Exception as e:
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
            except OSError:
                pass
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(wx.MessageBox, f"{i18n.tr('update_download_err')}\n\n{str(e)}", i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)

    threading.Thread(target=_download_thread, daemon=True).start()


def _apply_update_and_exit(parent, archive_path):
    """Generates the detached launcher updater script, runs it, and terminates the app."""
    pid = os.getpid()
    # Derive the app folder from the executable, not the CWD: a shortcut with a
    # different "Start in" directory would make the script delete and copy files
    # in the wrong folder.
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.abspath(os.getcwd())
    temp_dir = tempfile.gettempdir()

    if sys.platform == 'win32':
        # Resolve target executable path
        # If running from PyInstaller executable, sys.executable is the path to the EXE
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.join(app_dir, "Music separator.exe")
        
        if getattr(sys, 'frozen', False):
            # In PyInstaller, 7za.exe is bundled inside _internal\ffmpeg_bin or alongside exe
            candidates = [
                os.path.join(os.path.dirname(exe_path), "_internal", "ffmpeg_bin", "7za.exe"),
                os.path.join(os.path.dirname(exe_path), "ffmpeg_bin", "7za.exe"),
                os.path.join(getattr(sys, '_MEIPASS', ''), "ffmpeg_bin", "7za.exe"),
            ]
            original_7z_path = ""
            for c in candidates:
                if c and os.path.exists(c):
                    original_7z_path = c
                    break
            if not original_7z_path:
                original_7z_path = os.path.join(os.path.dirname(exe_path), "_internal", "ffmpeg_bin", "7za.exe")
        else:
            # Fallback for development/venv setup
            candidates = [
                os.path.join(app_dir, "ffmpeg_bin", "7za.exe"),
                os.path.join(app_dir, "_internal", "ffmpeg_bin", "7za.exe"),
            ]
            original_7z_path = ""
            for c in candidates:
                if c and os.path.exists(c):
                    original_7z_path = c
                    break
            if not original_7z_path:
                original_7z_path = os.path.join(app_dir, "ffmpeg_bin", "7za.exe")

        # Normalize all paths for batch execution
        exe_path = os.path.normpath(exe_path)
        original_7z_path = os.path.normpath(original_7z_path)
        archive_path = os.path.normpath(archive_path)
        app_dir = os.path.normpath(app_dir)

        update_bat_path = os.path.join(temp_dir, f"update_{pid}.bat")

        # Create batch script that handles both flat archives and archives nested inside a single root folder.
        # Implements B01: staging backup, xcopy error check, integrity verification, and automatic rollback.
        bat_content = f"""@echo off
set "UPDATER_LOG=%TEMP%\\ms_update_{pid}.log"
set "EXTRACT_DIR=%TEMP%\\ms_update_{pid}"
set "EXE_BACKUP_READY=0"
set "INTERNAL_BACKUP_READY=0"
set "FF_BACKUP_READY=0"
echo [%date% %time%] Update started > "%UPDATER_LOG%"
copy /y "{original_7z_path}" "%TEMP%\\7za_temp_updater.exe" >nul
if errorlevel 1 goto :fail
if not exist "%TEMP%\\7za_temp_updater.exe" (
    echo [%date% %time%] ERROR: failed to copy 7za.exe >> "%UPDATER_LOG%"
    goto :fail
)
:wait_loop
tasklist /FI "PID eq {pid}" | find "{pid}" >nul
if not errorlevel 1 (
    ping -n 2 127.0.0.1 >nul
    goto wait_loop
)

if exist "%EXTRACT_DIR%" rmdir /s /q "%EXTRACT_DIR%"
"%TEMP%\\7za_temp_updater.exe" x "{archive_path}" -o"%EXTRACT_DIR%" -y >> "%UPDATER_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: extraction failed >> "%UPDATER_LOG%"
    goto :fail
)

set "SRC_DIR=%EXTRACT_DIR%"
set "DIR_COUNT=0"
set "FILE_COUNT=0"
set "SINGLE_DIR="
for /d %%i in ("%EXTRACT_DIR%\\*") do (
    set /a DIR_COUNT+=1
    set "SINGLE_DIR=%%i"
)
for %%i in ("%EXTRACT_DIR%\\*") do (
    set /a FILE_COUNT+=1
)
if %DIR_COUNT%==1 if %FILE_COUNT%==0 set "SRC_DIR=%SINGLE_DIR%"

rem --- Verify extracted structure before touching existing installation ---
if not exist "%SRC_DIR%\\{os.path.basename(exe_path)}" goto :fail
if not exist "%SRC_DIR%\\_internal" goto :fail

rem --- Backup existing components (executable, _internal, ffmpeg_bin) before replacement ---
rem Never overwrite recovery files from an earlier failed update.
if exist "{exe_path}.bak" goto :recovery_required
if exist "{exe_path}.bak.part" goto :recovery_required
if exist "{app_dir}\\_internal_backup" goto :recovery_required
if exist "{app_dir}\\ffmpeg_bin_backup" goto :recovery_required
if not exist "{exe_path}" goto :fail
copy /y "{exe_path}" "{exe_path}.bak.part" >nul
if errorlevel 1 goto :backup_failed
fc /b "{exe_path}" "{exe_path}.bak.part" >nul
if errorlevel 1 goto :backup_failed
move /y "{exe_path}.bak.part" "{exe_path}.bak" >nul
if errorlevel 1 goto :backup_failed
set "EXE_BACKUP_READY=1"
:skip_exe_backup

if not exist "{app_dir}\\_internal" goto :skip_backup
move "{app_dir}\\_internal" "{app_dir}\\_internal_backup" >nul
if errorlevel 1 (
    echo [%date% %time%] ERROR: failed to backup _internal folder >> "%UPDATER_LOG%"
    goto :rollback
)
set "INTERNAL_BACKUP_READY=1"
:skip_backup

if not exist "{app_dir}\\ffmpeg_bin" goto :skip_ff_backup
move "{app_dir}\\ffmpeg_bin" "{app_dir}\\ffmpeg_bin_backup" >nul
if errorlevel 1 (
    echo [%date% %time%] ERROR: failed to backup ffmpeg_bin folder >> "%UPDATER_LOG%"
    goto :rollback
)
set "FF_BACKUP_READY=1"
:skip_ff_backup

rem --- Copy new files into app_dir ---
xcopy "%SRC_DIR%\\*" "{app_dir}" /s /e /y /h /r >> "%UPDATER_LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: xcopy failed with errorlevel %errorlevel% >> "%UPDATER_LOG%"
    goto :rollback
)

rem --- Verify that essential files exist after copying ---
if not exist "{exe_path}" goto :rollback
if not exist "{app_dir}\\_internal" goto :rollback

rem --- Success: clean up backups and temporary extraction folder ---
echo [%date% %time%] Update verified successfully. >> "%UPDATER_LOG%"
if exist "{exe_path}.bak" del "{exe_path}.bak" >nul 2>&1
if exist "{app_dir}\\_internal_backup" rmdir /s /q "{app_dir}\\_internal_backup" >nul 2>&1
if exist "{app_dir}\\ffmpeg_bin_backup" rmdir /s /q "{app_dir}\\ffmpeg_bin_backup" >nul 2>&1
rmdir /s /q "%EXTRACT_DIR%" >nul 2>&1
echo [%date% %time%] Update OK, restarting >> "%UPDATER_LOG%"
start "" "{exe_path}"
del "%TEMP%\\7za_temp_updater.exe" >nul 2>&1
rem Keep the small script beside its log for diagnostics; do not delete while executing.
exit /b 0

:rollback
echo [%date% %time%] Performing rollback to previous version >> "%UPDATER_LOG%"
if not "%EXE_BACKUP_READY%"=="1" goto :rb_exe_done
copy /y "{exe_path}.bak" "{exe_path}" >nul
if errorlevel 1 goto :recovery_required
fc /b "{exe_path}.bak" "{exe_path}" >nul
if errorlevel 1 goto :recovery_required
:rb_exe_done

if not "%INTERNAL_BACKUP_READY%"=="1" goto :rb_internal_done
if exist "{app_dir}\\_internal" rmdir /s /q "{app_dir}\\_internal"
if exist "{app_dir}\\_internal" goto :recovery_required
xcopy "{app_dir}\\_internal_backup\\*" "{app_dir}\\_internal\\" /s /e /i /y /h /r >nul
if errorlevel 1 goto :recovery_required
:rb_internal_done

if not "%FF_BACKUP_READY%"=="1" goto :rb_ff_done
if exist "{app_dir}\\ffmpeg_bin" rmdir /s /q "{app_dir}\\ffmpeg_bin"
if exist "{app_dir}\\ffmpeg_bin" goto :recovery_required
xcopy "{app_dir}\\ffmpeg_bin_backup\\*" "{app_dir}\\ffmpeg_bin\\" /s /e /i /y /h /r >nul
if errorlevel 1 goto :recovery_required
:rb_ff_done

rem Remove backups only after ALL components have been restored successfully.
if "%EXE_BACKUP_READY%"=="1" del "{exe_path}.bak" >nul 2>&1
if "%INTERNAL_BACKUP_READY%"=="1" rmdir /s /q "{app_dir}\\_internal_backup" >nul 2>&1
if "%FF_BACKUP_READY%"=="1" rmdir /s /q "{app_dir}\\ffmpeg_bin_backup" >nul 2>&1
rmdir /s /q "%EXTRACT_DIR%" >nul 2>&1
echo [%date% %time%] Rollback completed, restarting previous version >> "%UPDATER_LOG%"
start "" "{exe_path}"
del "%TEMP%\\7za_temp_updater.exe" >nul 2>&1
exit /b 1

:fail
echo [%date% %time%] Update ABORTED, restoring any backups >> "%UPDATER_LOG%"
goto :rollback

:backup_failed
echo [%date% %time%] Backup failed verification; original installation unchanged >> "%UPDATER_LOG%"
rem An incomplete .part file is never used for recovery.
if exist "{exe_path}.bak.part" del "{exe_path}.bak.part" >nul 2>&1
goto :fail

:recovery_required
echo [%date% %time%] ERROR: recovery required. Backups preserved in {app_dir} >> "%UPDATER_LOG%"
rem Do not restart a potentially mixed installation or discard recovery data.
exit /b 2
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

        # Mac updater script: unzips to a unique temp directory, verifies bundle structure,
        # backs up the existing .app before replacement, and rolls back if replacement fails.
        sh_content = f"""#!/bin/bash
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done

EXTRACT_DIR="/tmp/ms_update_{pid}"
BACKUP_APP="{target_dir}/Music_separator_backup.app"

rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"

unzip -q -o "{archive_path}" -d "$EXTRACT_DIR"
if [ $? -ne 0 ]; then
    echo "Extraction failed"
    rm -rf "$EXTRACT_DIR"
    {app_relaunch_cmd}
    rm "$0"
    exit 1
fi

EXTRACTED_APP=$(find "$EXTRACT_DIR" -name "*.app" -type d -maxdepth 2 | head -n 1)
if [ -z "$EXTRACTED_APP" ] || [ ! -d "$EXTRACTED_APP" ]; then
    echo "No valid .app found in archive"
    rm -rf "$EXTRACT_DIR"
    {app_relaunch_cmd}
    rm "$0"
    exit 1
fi

if [ ! -f "$EXTRACTED_APP/Contents/Info.plist" ] || [ ! -d "$EXTRACTED_APP/Contents/MacOS" ]; then
    echo "Extracted .app structure invalid"
    rm -rf "$EXTRACT_DIR"
    {app_relaunch_cmd}
    rm "$0"
    exit 1
fi

# Backup existing app
if [ -d "{app_bundle_path}" ]; then
    rm -rf "$BACKUP_APP"
    mv "{app_bundle_path}" "$BACKUP_APP"
    if [ $? -ne 0 ]; then
        echo "Failed to backup existing app"
        rm -rf "$EXTRACT_DIR"
        {app_relaunch_cmd}
        rm "$0"
        exit 1
    fi
fi

# Move new app to target dir
mv "$EXTRACTED_APP" "{target_dir}/"
MOVE_STATUS=$?

if [ $MOVE_STATUS -ne 0 ] || [ ! -d "{app_bundle_path}" ]; then
    echo "Installation failed, rolling back"
    if [ -d "$BACKUP_APP" ]; then
        rm -rf "{app_bundle_path}"
        mv "$BACKUP_APP" "{app_bundle_path}"
    fi
    rm -rf "$EXTRACT_DIR"
    {app_relaunch_cmd}
    rm "$0"
    exit 1
fi

# Success: remove backup and temp
rm -rf "$BACKUP_APP"
rm -rf "$EXTRACT_DIR"
{app_relaunch_cmd}
rm "$0"
exit 0
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
