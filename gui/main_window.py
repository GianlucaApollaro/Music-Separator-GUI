import wx
import os
import json
import threading
from gui.worker import SeparationThread
from gui.events import EVT_LOG_ID, EVT_DONE_ID, EVT_PROGRESS_ID
from gui.i18n_manager import i18n
from gui.utils import download_file
from gui.preset_manager import PresetManager
from gui.model_manager import ModelManager
from gui.config_manager import config

class MainWindow(wx.Frame):
    def __init__(self, parent, title):
        super(MainWindow, self).__init__(parent, title=i18n.tr("app_title"), size=(600, 600))
        
        self.worker = None
        self.model_manager = ModelManager()

        self.InitUI()
        self.InitMenu()
        self.Centre()
        self.OnPresetChange(None)  # Applica lo stato del preset salvato all'avvio
        
        # Bind Custom Events
        self.Connect(-1, -1, EVT_LOG_ID, self.OnLog)
        self.Connect(-1, -1, EVT_DONE_ID, self.OnDone)
        self.Connect(-1, -1, EVT_PROGRESS_ID, self.OnProgress)

        self.model_manager.add_ready_callback(self._populate_model_combobox)

    def _populate_model_combobox(self):
        old_val_1 = self.cb_model.GetValue()
        old_val_2 = self.cb_model_2.GetValue()
        
        self.model_list = self.model_manager.get_model_list()
        
        self.cb_model.Clear()
        self.cb_model_2.Clear()
        for m in self.model_list:
            self.cb_model.Append(m)
            self.cb_model_2.Append(m)
            
        if old_val_1 in self.model_list:
            self.cb_model.SetValue(old_val_1)
        else:
            self.cb_model.SetValue(config.get("model_1", self.model_list[0]))
            
        if old_val_2 in self.model_list:
            self.cb_model_2.SetValue(old_val_2)
        else:
            self.cb_model_2.SetValue(config.get("model_2", self.model_list[-1] if self.model_list else ""))

    def InitMenu(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        
        # Language Submenu
        langMenu = wx.Menu()
        enItem = langMenu.Append(wx.ID_ANY, i18n.tr("menu_english"), kind=wx.ITEM_RADIO)
        itItem = langMenu.Append(wx.ID_ANY, i18n.tr("menu_italian"), kind=wx.ITEM_RADIO)
        esItem = langMenu.Append(wx.ID_ANY, i18n.tr("menu_spanish"), kind=wx.ITEM_RADIO)
        
        if i18n.current_lang == 'en':
            enItem.Check()
        elif i18n.current_lang == 'es':
            esItem.Check()
        else:
            itItem.Check()

        self.Bind(wx.EVT_MENU, lambda e: self.OnLanguageChange('en'), enItem)
        self.Bind(wx.EVT_MENU, lambda e: self.OnLanguageChange('it'), itItem)
        self.Bind(wx.EVT_MENU, lambda e: self.OnLanguageChange('es'), esItem)

        fileMenu.AppendSubMenu(langMenu, i18n.tr("menu_language"))
        menubar.Append(fileMenu, i18n.tr("menu_file"))
        self.SetMenuBar(menubar)

    def InitUI(self):
        self.panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Input File ---
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        self.st1 = wx.StaticText(self.panel, label=i18n.tr("input_audio"))
        hbox1.Add(self.st1, flag=wx.RIGHT, border=8)
        self.tc_input = wx.TextCtrl(self.panel)
        hbox1.Add(self.tc_input, proportion=1)
        self.btn_input = wx.Button(self.panel, label=i18n.tr("browse"))
        self.btn_input.Bind(wx.EVT_BUTTON, self.OnBrowseInput)
        hbox1.Add(self.btn_input, flag=wx.LEFT, border=5)
        
        self.btn_input_dir = wx.Button(self.panel, label=i18n.tr("browse_folder"))
        self.btn_input_dir.Bind(wx.EVT_BUTTON, self.OnBrowseInputDir)
        hbox1.Add(self.btn_input_dir, flag=wx.LEFT, border=5)
        vbox.Add(hbox1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Output Dir ---
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.st2 = wx.StaticText(self.panel, label=i18n.tr("output_dir"))
        hbox2.Add(self.st2, flag=wx.RIGHT, border=15) # align with above
        self.tc_output = wx.TextCtrl(self.panel)
        # Default to configured folder or inside project folder
        self.tc_output.SetValue(config.get("output_dir", os.path.join(os.getcwd(), 'output')))
        hbox2.Add(self.tc_output, proportion=1)
        self.btn_output = wx.Button(self.panel, label=i18n.tr("browse"))
        self.btn_output.Bind(wx.EVT_BUTTON, self.OnBrowseOutput)
        hbox2.Add(self.btn_output, flag=wx.LEFT, border=5)
        vbox.Add(hbox2, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Model Selection ---
        hbox3 = wx.BoxSizer(wx.HORIZONTAL)
        self.st3 = wx.StaticText(self.panel, label=i18n.tr("model"))
        hbox3.Add(self.st3, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=25)
        
        self.model_list = self.model_manager.get_model_list()

        self.cb_model = wx.ComboBox(self.panel, choices=self.model_list, style=wx.CB_DROPDOWN)
        self.cb_model.SetValue(config.get("model_1", self.model_list[0] if self.model_list else "")) # Default
        self.cb_model.SetToolTip(i18n.tr("model_tooltip"))
        hbox3.Add(self.cb_model, proportion=1, flag=wx.EXPAND)
        vbox.Add(hbox3, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Ensemble Option ---
        hbox_ens_chk = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_ensemble = wx.CheckBox(self.panel, label=i18n.tr("enable_ensemble"))
        self.chk_ensemble.SetValue(config.get("enable_ensemble", False))
        self.chk_ensemble.Bind(wx.EVT_CHECKBOX, self.OnEnsembleCheck)
        hbox_ens_chk.Add(self.chk_ensemble, flag=wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(hbox_ens_chk, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Secondary Model (Ensemble) ---
        hbox_ens_mod = wx.BoxSizer(wx.HORIZONTAL)
        self.st_model_2 = wx.StaticText(self.panel, label=i18n.tr("secondary_model"))
        hbox_ens_mod.Add(self.st_model_2, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.cb_model_2 = wx.ComboBox(self.panel, choices=self.model_list, style=wx.CB_DROPDOWN)
        if config.get("model_2", "") in self.model_list:
            self.cb_model_2.SetValue(config.get("model_2", ""))
        elif len(self.model_list) > 1:
            self.cb_model_2.SetValue(self.model_list[1])
        else:
            self.cb_model_2.SetValue(self.model_list[0] if self.model_list else "")
        self.cb_model_2.Disable()
        self.st_model_2.Disable()
        hbox_ens_mod.Add(self.cb_model_2, proportion=1, flag=wx.EXPAND)
        vbox.Add(hbox_ens_mod, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Ensemble Algorithm ---
        self.ensemble_algorithms = [
            "avg_wave", "min_wave", "max_wave", "median_wave"
        ]
        hbox_ens_algo = wx.BoxSizer(wx.HORIZONTAL)
        self.st_ens_algo = wx.StaticText(self.panel, label=i18n.tr("ensemble_algorithm"))
        hbox_ens_algo.Add(self.st_ens_algo, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.cb_ens_algo = wx.ComboBox(self.panel, choices=self.ensemble_algorithms, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.cb_ens_algo.SetValue("avg_wave")
        self.cb_ens_algo.SetToolTip(i18n.tr("ensemble_algorithm_tooltip"))
        self.cb_ens_algo.Disable()
        self.st_ens_algo.Disable()
        hbox_ens_algo.Add(self.cb_ens_algo, proportion=1, flag=wx.EXPAND)
        vbox.Add(hbox_ens_algo, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Pre-set Selection ---
        self.hbox_preset = wx.BoxSizer(wx.HORIZONTAL)
        self.st_preset = wx.StaticText(self.panel, label=i18n.tr("preset_label"))
        self.hbox_preset.Add(self.st_preset, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=25)
        
        self.cb_preset = wx.ComboBox(self.panel, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        for key in PresetManager.preset_keys:
            self.cb_preset.Append(i18n.tr(key))
        self.cb_preset.SetSelection(config.get("preset", 0))
        self.cb_preset.Bind(wx.EVT_COMBOBOX, self.OnPresetChange)
        self.hbox_preset.Add(self.cb_preset, proportion=1, flag=wx.EXPAND)
        vbox.Add(self.hbox_preset, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Options ---
        hbox4 = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_gpu = wx.CheckBox(self.panel, label=i18n.tr("use_gpu"))
        
        # Check GPU availability: CUDA (Windows/Linux) or MPS (Apple Silicon)
        import torch
        has_cuda = torch.cuda.is_available()
        has_mps = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        has_gpu = has_cuda or has_mps
        if has_gpu:
            self.chk_gpu.SetValue(True)
            if has_mps and not has_cuda:
                self.chk_gpu.SetToolTip(i18n.tr("gpu_mps_tooltip"))
        else:
            self.chk_gpu.SetValue(False)
            self.chk_gpu.Disable()
            self.chk_gpu.SetToolTip(i18n.tr("gpu_not_available_tooltip"))
            
        hbox4.Add(self.chk_gpu)

        self.chk_remove_numbers = wx.CheckBox(self.panel, label=i18n.tr("remove_leading_numbers"))
        self.chk_remove_numbers.SetValue(config.get("remove_leading_numbers", False))
        hbox4.Add(self.chk_remove_numbers, flag=wx.LEFT, border=15)
        
        hbox4.AddStretchSpacer(prop=1)
        self.st_format = wx.StaticText(self.panel, label=i18n.tr("output_format"))
        hbox4.Add(self.st_format, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.cb_format = wx.ComboBox(self.panel, choices=['WAV', 'FLAC', 'MP3'], style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.cb_format.SetValue(config.get("output_format", 'WAV'))
        hbox4.Add(self.cb_format)

        vbox.Add(hbox4, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Chunk Duration ---
        self.chunk_values = [60, 120, 300, 600, 900, 1200]
        self.chunk_choices = ["1 min", "2 min", "5 min", "10 min", "15 min", "20 min"]
        hbox_chunk = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_chunk = wx.CheckBox(self.panel, label=i18n.tr("chunk_enable"))
        self.chk_chunk.SetValue(config.get("chunk_enable", False))
        self.chk_chunk.Bind(wx.EVT_CHECKBOX, self.OnChunkCheck)
        hbox_chunk.Add(self.chk_chunk, flag=wx.ALIGN_CENTER_VERTICAL)
        hbox_chunk.AddStretchSpacer(prop=1)
        self.st_chunk_dur = wx.StaticText(self.panel, label=i18n.tr("chunk_duration_label"))
        hbox_chunk.Add(self.st_chunk_dur, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=8)
        self.cb_chunk = wx.ComboBox(self.panel, choices=self.chunk_choices, style=wx.CB_DROPDOWN | wx.CB_READONLY, size=(90, -1))
        self.cb_chunk.SetSelection(config.get("chunk_size_idx", 0))  # Default: 1 min
        
        if not self.chk_chunk.GetValue():
            self.st_chunk_dur.Disable()
            self.cb_chunk.Disable()
            
        hbox_chunk.Add(self.cb_chunk, flag=wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(hbox_chunk, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Buttons ---
        hbox5 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self.panel, label=i18n.tr("start_separation"))
        self.btn_start.Bind(wx.EVT_BUTTON, self.OnStart)
        hbox5.Add(self.btn_start, proportion=1)
        
        self.btn_stop = wx.Button(self.panel, label=i18n.tr("stop"))
        self.btn_stop.Bind(wx.EVT_BUTTON, self.OnStop)
        self.btn_stop.Disable()
        hbox5.Add(self.btn_stop, flag=wx.LEFT, border=10)
        
        vbox.Add(hbox5, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=15)

        # --- Progress Bar ---
        self.gauge = wx.Gauge(self.panel, range=100, size=(250, 15))
        vbox.Add(self.gauge, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=15)

        # --- Log / Output ---
        self.st_log = wx.StaticText(self.panel, label=i18n.tr("logs"))
        vbox.Add(self.st_log, flag=wx.LEFT|wx.TOP, border=10)
        
        self.tc_log = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
        font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.tc_log.SetFont(font)
        vbox.Add(self.tc_log, proportion=1, flag=wx.EXPAND|wx.ALL, border=10)

        self.panel.SetSizer(vbox)

    def OnEnsembleCheck(self, event):
        is_checked = self.chk_ensemble.GetValue()
        if is_checked:
            self.cb_model_2.Enable()
            self.st_model_2.Enable()
            self.cb_ens_algo.Enable()
            self.st_ens_algo.Enable()
            self.cb_preset.Hide()
            self.st_preset.Hide()
        else:
            self.cb_model_2.Disable()
            self.st_model_2.Disable()
            self.cb_ens_algo.Disable()
            self.st_ens_algo.Disable()
            self.cb_preset.Show()
            self.st_preset.Show()
        self.panel.Layout()
        config.set("enable_ensemble", is_checked)

    def OnChunkCheck(self, event):
        is_checked = self.chk_chunk.GetValue()
        if is_checked:
            self.st_chunk_dur.Enable()
            self.cb_chunk.Enable()
        else:
            self.st_chunk_dur.Disable()
            self.cb_chunk.Disable()

    def OnPresetChange(self, event):
        idx = self.cb_preset.GetSelection()
        preset_key = PresetManager.preset_keys[idx]
        if preset_key != "preset_none":
            self.cb_model.Disable()
            self.st3.Disable()
        else:
            self.cb_model.Enable()
            self.st3.Enable()

    def UpdateLabels(self):
        self.SetTitle(i18n.tr("app_title"))
        self.st1.SetLabel(i18n.tr("input_audio"))
        self.btn_input.SetLabel(i18n.tr("browse"))
        self.btn_input_dir.SetLabel(i18n.tr("browse_folder"))
        self.st2.SetLabel(i18n.tr("output_dir"))
        self.btn_output.SetLabel(i18n.tr("browse"))
        self.st3.SetLabel(i18n.tr("model"))
        self.chk_ensemble.SetLabel(i18n.tr("enable_ensemble"))
        self.st_model_2.SetLabel(i18n.tr("secondary_model"))
        self.st_ens_algo.SetLabel(i18n.tr("ensemble_algorithm"))
        self.cb_ens_algo.SetToolTip(i18n.tr("ensemble_algorithm_tooltip"))
        self.chk_gpu.SetLabel(i18n.tr("use_gpu"))
        self.chk_remove_numbers.SetLabel(i18n.tr("remove_leading_numbers"))
        self.st_format.SetLabel(i18n.tr("output_format"))
        self.chk_chunk.SetLabel(i18n.tr("chunk_enable"))
        self.st_chunk_dur.SetLabel(i18n.tr("chunk_duration_label"))
        self.btn_start.SetLabel(i18n.tr("start_separation"))
        self.btn_stop.SetLabel(i18n.tr("stop"))
        self.st_log.SetLabel(i18n.tr("logs"))
        
        self.cb_model.SetToolTip(i18n.tr("model_tooltip"))
        if self.chk_gpu.IsEnabled():
            # Only if it was MPS
            import torch
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() and not torch.cuda.is_available():
                self.chk_gpu.SetToolTip(i18n.tr("gpu_mps_tooltip"))
        else:
            self.chk_gpu.SetToolTip(i18n.tr("gpu_not_available_tooltip"))
        
        self.st_preset.SetLabel(i18n.tr("preset_label"))
        old_sel = self.cb_preset.GetSelection()
        if old_sel == wx.NOT_FOUND:
            old_sel = 0
        self.cb_preset.Clear()
        for key in PresetManager.preset_keys:
            self.cb_preset.Append(i18n.tr(key))
        self.cb_preset.SetSelection(old_sel)
        
        # Re-init menu to update labels there too
        self.SetMenuBar(None)
        self.InitMenu()
        self.panel.Layout()

    def OnLanguageChange(self, lang_code):
        i18n.load_language(lang_code)
        self.UpdateLabels()

    def OnBrowseInput(self, event):
        with wx.FileDialog(self, i18n.tr("open_media_files"), wildcard="Media files (*.mp3;*.wav;*.flac;*.m4a;*.mp4;*.mkv)|*.mp3;*.wav;*.flac;*.m4a;*.mp4;*.mkv",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            paths = fileDialog.GetPaths()
            self.tc_input.SetValue("|".join(paths))

    def OnBrowseInputDir(self, event):
        with wx.DirDialog(self, i18n.tr("choose_input_dir"),
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dirDialog.GetPath()
            valid_exts = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.mp4', '.mkv']
            audio_files = []
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if any(f.lower().endswith(ext) for ext in valid_exts):
                        audio_files.append(os.path.join(root, f))
            if audio_files:
                self.tc_input.SetValue("|".join(audio_files))
            else:
                wx.MessageBox(i18n.tr("no_audio_files_found"), i18n.tr("msg_no_files"), wx.OK | wx.ICON_WARNING)

    def OnBrowseOutput(self, event):
        with wx.DirDialog(self, i18n.tr("choose_output_dir"),
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            self.tc_output.SetValue(dirDialog.GetPath())

    def OnLog(self, event):
        self.tc_log.AppendText(event.message + "\n")

    def OnProgress(self, event):
        self.gauge.SetRange(event.maximum)
        self.gauge.SetValue(event.value)

    def OnDone(self, event):
        self.worker = None
        self.btn_start.Enable()
        self.btn_stop.Disable()
        self.gauge.SetValue(100)
        if event.success:
            wx.MessageBox(i18n.tr("msg_success"), i18n.tr("msg_success_title"), wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox(i18n.tr("msg_error"), i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)

    def OnStart(self, event):
        input_string = self.tc_input.GetValue()
        output_dir = self.tc_output.GetValue().strip().strip('"')
        model_name = self.cb_model.GetValue()

        # Save user configuration
        config.set("output_dir", output_dir)
        config.set("model_1", model_name)
        config.set("model_2", self.cb_model_2.GetValue())
        config.set("preset", self.cb_preset.GetSelection())
        config.set("enable_ensemble", self.chk_ensemble.GetValue())
        config.set("output_format", self.cb_format.GetValue())
        config.set("remove_leading_numbers", self.chk_remove_numbers.GetValue())
        config.set("chunk_enable", self.chk_chunk.GetValue())
        config.set("chunk_size_idx", self.cb_chunk.GetSelection())

        if not input_string:
            wx.MessageBox(i18n.tr("msg_select_input"), i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
            return

        input_files = [p.strip().strip('"') for p in input_string.split("|") if os.path.exists(p.strip().strip('"'))]
        if not input_files:
            wx.MessageBox(i18n.tr("msg_select_input"), i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
            return

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError:
                wx.MessageBox(i18n.tr("msg_create_output_err"), i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
                return

        # Resolve chunk_duration
        chunk_duration = None
        if self.chk_chunk.GetValue():
            idx = self.cb_chunk.GetSelection()
            chunk_duration = self.chunk_values[idx] if idx != wx.NOT_FOUND else 60

        self.tc_log.Clear()
        self.gauge.SetValue(0)
        self.btn_start.Disable()
        self.btn_stop.Enable()

        preset_config = None
        preset_idx = self.cb_preset.GetSelection()
        if not self.chk_ensemble.GetValue() and preset_idx > 0:
            preset_key = PresetManager.preset_keys[preset_idx]
            preset_config = PresetManager.get_preset_config(preset_key)

        out_format = self.cb_format.GetValue()
        use_gpu = self.chk_gpu.GetValue()
        use_ensemble = self.chk_ensemble.GetValue()
        model_name_2 = self.cb_model_2.GetValue()
        ensemble_algorithm = self.cb_ens_algo.GetValue()
        remove_leading_numbers = self.chk_remove_numbers.GetValue()

        # Thread-safe callbacks
        def logger_cb(msg):
            wx.CallAfter(self.tc_log.AppendText, msg)

        def progress_cb(current, total):
            if total > 0:
                percent = int((current / total) * 100)
                wx.CallAfter(self.gauge.SetValue, percent)

        def _abort():
            wx.CallAfter(self.btn_start.Enable)
            wx.CallAfter(self.btn_stop.Disable)

        def _download_and_launch():
            """Background thread: resolves/downloads models, then starts SeparationThread."""
            if preset_config:
                m1 = self.model_manager.resolve_and_download(preset_config["model_1"], logger_cb, progress_cb)
                if not m1:
                    _abort()
                    return
                m2 = self.model_manager.resolve_and_download(preset_config["model_2"], logger_cb, progress_cb)
                if not m2:
                    _abort()
                    return
                m3 = None
                if "model_3" in preset_config:
                    m3 = self.model_manager.resolve_and_download(preset_config["model_3"], logger_cb, progress_cb)
                    if not m3:
                        _abort()
                        return

                def _start_preset():
                    self.worker = SeparationThread(
                        self, input_files, output_dir, m1, use_gpu, out_format,
                        m2, m3, preset_config, chunk_duration=chunk_duration,
                        remove_leading_numbers=remove_leading_numbers
                    )
                    self.worker.start()
                wx.CallAfter(_start_preset)
                return

            # Standard or ensemble
            m1 = self.model_manager.resolve_and_download(model_name, logger_cb, progress_cb)
            if not m1:
                _abort()
                return

            m2 = None
            algo = "avg_wave"
            if use_ensemble:
                m2 = self.model_manager.resolve_and_download(model_name_2, logger_cb, progress_cb)
                if not m2:
                    _abort()
                    return
                algo = ensemble_algorithm

            def _start_standard():
                self.worker = SeparationThread(
                    self, input_files, output_dir, m1, use_gpu, out_format,
                    m2, ensemble_algorithm=algo, chunk_duration=chunk_duration,
                    remove_leading_numbers=remove_leading_numbers
                )
                self.worker.start()
            wx.CallAfter(_start_standard)

        threading.Thread(target=_download_and_launch, daemon=True).start()

    def OnStop(self, event):
        if self.worker:
            self.worker.stop()
            self.tc_log.AppendText(i18n.tr("msg_stopping") + "\n")
