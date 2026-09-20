import sys
import wx
import os
from gui.preset_manager import PresetManager
from gui.audio_utils import get_model_stems

class CustomPresetDialog(wx.Dialog):
    def __init__(self, parent, model_list, i18n, model_manager=None):
        super().__init__(parent, title=i18n.tr("preset_create_title"), size=(550, 650),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.model_list = model_list
        self.i18n = i18n
        self.model_manager = model_manager
        self.steps = [] # List of dicts representing chain steps GUI elements
        
        self.init_ui()
        self.center_on_parent()
        
    def center_on_parent(self):
        parent = self.GetParent()
        if parent:
            self.CenterOnParent()
        else:
            self.Center()

    def get_model_stems(self, model_name: str) -> list:
        return get_model_stems(model_name)

    def _resolve(self, name: str) -> str:
        """Resolve a model display name to its actual filename using model_manager if available."""
        if self.model_manager:
            return self.model_manager.resolve_model_filename(name)
        return name

    def init_ui(self):

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Scrollable container for the form
        scroll_win = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.BORDER_NONE)
        scroll_win.SetScrollRate(0, 20)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- Preset Name ---
        lbl_name = wx.StaticText(scroll_win, label=self.i18n.tr("preset_name_label"))
        self.txt_name = wx.TextCtrl(scroll_win)
        
        scroll_sizer.Add(lbl_name, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=15)
        scroll_sizer.Add(self.txt_name, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        # --- Preset Type ---
        lbl_type = wx.StaticText(scroll_win, label=self.i18n.tr("preset_type_label"))
        self.cb_type = wx.Choice(scroll_win, choices=[
            self.i18n.tr("preset_type_single"),
            self.i18n.tr("preset_type_chain")
        ])
        self.cb_type.SetSelection(0)
        self.cb_type.Bind(wx.EVT_CHOICE, self.on_type_change)
        
        scroll_sizer.Add(lbl_type, flag=wx.LEFT | wx.RIGHT, border=15)
        scroll_sizer.Add(self.cb_type, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        # --- Single Model Panel ---
        self.panel_single = wx.Panel(scroll_win)
        self.init_single_panel()
        scroll_sizer.Add(self.panel_single, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        # --- Chained Models Panel ---
        self.panel_chain = wx.Panel(scroll_win)
        self.init_chain_panel()
        self.panel_chain.Hide()
        scroll_sizer.Add(self.panel_chain, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        scroll_win.SetSizer(scroll_sizer)
        main_sizer.Add(scroll_win, proportion=1, flag=wx.EXPAND)
        
        # --- Dialog Buttons ---
        btn_sizer = wx.StdDialogButtonSizer()
        
        self.btn_save = wx.Button(self, wx.ID_OK, label=self.i18n.tr("preset_save"))
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label=self.i18n.tr("preset_cancel"))
        
        btn_sizer.AddButton(self.btn_save)
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=15)
        
        self.SetSizer(main_sizer)
        
    def init_single_panel(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        lbl_model = wx.StaticText(self.panel_single, label=self.i18n.tr("preset_model_select"))
        if sys.platform == 'darwin':
            self.cb_single_model = wx.Choice(self.panel_single)
            self.cb_single_model.Bind(wx.EVT_CHOICE, lambda evt: self.update_single_rename_fields())
        else:
            self.cb_single_model = wx.ComboBox(self.panel_single, style=wx.CB_DROPDOWN | wx.CB_READONLY)
            self.cb_single_model.Bind(wx.EVT_COMBOBOX, lambda evt: self.update_single_rename_fields())
        self.cb_single_model.SetName(self.i18n.tr("preset_model_select"))
        self.cb_single_model.AppendItems(self.model_list)
        
        sizer.Add(lbl_model, flag=wx.TOP, border=5)
        sizer.Add(self.cb_single_model, flag=wx.EXPAND | wx.BOTTOM, border=15)
        
        # Dynamic Rename Map Container
        self.single_rename_container = wx.Panel(self.panel_single)
        self.single_rename_sizer = wx.BoxSizer(wx.VERTICAL)
        self.single_rename_container.SetSizer(self.single_rename_sizer)
        self.single_rename_fields = {}
        
        sizer.Add(self.single_rename_container, flag=wx.EXPAND | wx.BOTTOM, border=15)
        
        # Mix Remaining option
        self.chk_mix = wx.CheckBox(self.panel_single, label=self.i18n.tr("preset_mix_remaining"))
        self.chk_mix.Bind(wx.EVT_CHECKBOX, self.on_toggle_mix)
        
        self.lbl_mix_target = wx.StaticText(self.panel_single, label=self.i18n.tr("preset_mix_remaining_label"))
        self.txt_mix_target = wx.TextCtrl(self.panel_single, value="_No_Drums")
        self.lbl_mix_target.Disable()
        self.txt_mix_target.Disable()
        
        sizer.Add(self.chk_mix, flag=wx.BOTTOM, border=5)
        sizer.Add(self.lbl_mix_target, flag=wx.LEFT, border=15)
        sizer.Add(self.txt_mix_target, flag=wx.EXPAND | wx.LEFT | wx.BOTTOM, border=15)
        
        self.panel_single.SetSizer(sizer)
        
        if self.model_list:
            self.cb_single_model.SetSelection(0)
            self.update_single_rename_fields()

    def update_single_rename_fields(self):
        # Clear previous fields and destroy windows
        self.single_rename_sizer.Clear(True)
        self.single_rename_fields = {}
        
        model = self.cb_single_model.GetStringSelection()
        stems = self.get_model_stems(model)
        
        lbl_rename = wx.StaticText(self.single_rename_container, label=self.i18n.tr("preset_rename_title"))
        self.single_rename_sizer.Add(lbl_rename, flag=wx.BOTTOM, border=5)
        
        grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=8)
        grid.AddGrowableCol(1, 1)
        
        for stem in stems:
            lbl_stem = wx.StaticText(self.single_rename_container, label=stem)
            txt_suffix = wx.TextCtrl(self.single_rename_container)
            txt_suffix.SetHint(f"e.g. _{stem.capitalize()}")
            grid.Add(lbl_stem, flag=wx.ALIGN_CENTER_VERTICAL)
            grid.Add(txt_suffix, flag=wx.EXPAND)
            self.single_rename_fields[stem] = txt_suffix
            
        self.single_rename_sizer.Add(grid, flag=wx.EXPAND)
        self.single_rename_container.Layout()
        self.panel_single.Layout()
        self.Layout()

        
    def init_chain_panel(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Area where dynamic steps will be added
        self.steps_container = wx.Panel(self.panel_chain)
        self.steps_sizer = wx.BoxSizer(wx.VERTICAL)
        self.steps_container.SetSizer(self.steps_sizer)
        
        sizer.Add(self.steps_container, proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=10)
        
        # Buttons to add/remove steps
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_step = wx.Button(self.panel_chain, label=self.i18n.tr("preset_add_step"))
        self.btn_add_step.Bind(wx.EVT_BUTTON, self.on_add_step)
        
        self.btn_remove_step = wx.Button(self.panel_chain, label=self.i18n.tr("preset_remove_step"))
        self.btn_remove_step.Bind(wx.EVT_BUTTON, self.on_remove_step)
        
        btn_box.Add(self.btn_add_step, flag=wx.RIGHT, border=10)
        btn_box.Add(self.btn_remove_step)
        
        sizer.Add(btn_box, flag=wx.ALIGN_RIGHT | wx.BOTTOM, border=15)
        
        self.panel_chain.SetSizer(sizer)
        
        # Add initial 2 steps by default
        self.add_chain_step_ui()
        self.add_chain_step_ui()
        
    def on_type_change(self, event):
        sel = self.cb_type.GetSelection()
        if sel == 0:
            self.panel_single.Show()
            self.panel_chain.Hide()
        else:
            self.panel_single.Hide()
            self.panel_chain.Show()
        self.Layout()
        
    def on_toggle_mix(self, event):
        enabled = self.chk_mix.GetValue()
        self.lbl_mix_target.Enable(enabled)
        self.txt_mix_target.Enable(enabled)

    def on_add_step(self, event):
        if len(self.steps) < 5:  # Max 5 steps
            self.add_chain_step_ui()
        
    def on_remove_step(self, event):
        if len(self.steps) > 2: # Keep at least 2 steps for a chain
            step_ui = self.steps.pop()
            
            # Destroy all windows/widgets associated with the step
            if step_ui.get("lbl_source"):
                step_ui["lbl_source"].Destroy()
            if step_ui.get("cb_source"):
                step_ui["cb_source"].Destroy()
            step_ui["cb_model"].Destroy()
            step_ui["cb_pass"].Destroy()
            step_ui["rename_container"].Destroy()
            step_ui["lbl_model"].Destroy()
            step_ui["lbl_pass"].Destroy()
            step_ui["lbl_keep"].Destroy()
            
            try:
                step_ui["static_box"].Destroy()
            except RuntimeError:
                pass
                
            # Remove sizer from parent steps_sizer
            self.steps_sizer.Remove(step_ui["box_sizer"])
            
            self.update_steps_visibility()
            self.steps_sizer.Layout()
            self.panel_chain.Layout()
            self.Layout()
            
    def add_chain_step_ui(self):
        step_num = len(self.steps) + 1
        
        box = wx.StaticBox(self.steps_container, label=self.i18n.tr("preset_step_title").format(num=step_num))
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        # Source audio selector (for step 2 and beyond)
        lbl_source = None
        cb_source = None
        if step_num > 1:
            lbl_source = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_source_label"))
            if sys.platform == 'darwin':
                cb_source = wx.Choice(self.steps_container)
                cb_source.Bind(wx.EVT_CHOICE, self.on_source_change_evt)
            else:
                cb_source = wx.ComboBox(self.steps_container, style=wx.CB_DROPDOWN | wx.CB_READONLY)
                cb_source.Bind(wx.EVT_COMBOBOX, self.on_source_change_evt)
            cb_source.SetName(self.i18n.tr("preset_source_label"))
            box_sizer.Add(lbl_source, flag=wx.TOP, border=2)
            box_sizer.Add(cb_source, flag=wx.EXPAND | wx.BOTTOM, border=8)

        # Model selector
        lbl_model = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_model_select"))
        if sys.platform == 'darwin':
            cb_model = wx.Choice(self.steps_container)
            cb_model.Bind(wx.EVT_CHOICE, self.on_step_model_change_evt)
        else:
            cb_model = wx.ComboBox(self.steps_container, style=wx.CB_DROPDOWN | wx.CB_READONLY)
            cb_model.Bind(wx.EVT_COMBOBOX, self.on_step_model_change_evt)
        cb_model.SetName(self.i18n.tr("preset_model_select"))
        cb_model.AppendItems(self.model_list)
        
        box_sizer.Add(lbl_model, flag=wx.TOP, border=2)
        box_sizer.Add(cb_model, flag=wx.EXPAND | wx.BOTTOM, border=8)
        
        # Intermediate settings
        lbl_pass = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_pass_stem"))
        if sys.platform == 'darwin':
            cb_pass = wx.Choice(self.steps_container)
            cb_pass.Bind(wx.EVT_CHOICE, self.on_pass_stem_change_evt)
        else:
            cb_pass = wx.ComboBox(self.steps_container, style=wx.CB_DROPDOWN | wx.CB_READONLY)
            cb_pass.Bind(wx.EVT_COMBOBOX, self.on_pass_stem_change_evt)
        cb_pass.SetName(self.i18n.tr("preset_pass_stem"))
        
        lbl_keep = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_keep_rename_title"))
        rename_container = wx.Panel(self.steps_container)
        rename_sizer = wx.BoxSizer(wx.VERTICAL)
        rename_container.SetSizer(rename_sizer)
        
        box_sizer.Add(lbl_pass, flag=wx.TOP, border=2)
        box_sizer.Add(cb_pass, flag=wx.EXPAND | wx.BOTTOM, border=8)
        box_sizer.Add(lbl_keep, flag=wx.TOP, border=2)
        box_sizer.Add(rename_container, flag=wx.EXPAND | wx.BOTTOM, border=5)
        
        self.steps_sizer.Add(box_sizer, flag=wx.EXPAND | wx.BOTTOM, border=10)
        
        step_dict = {
            "box_sizer": box_sizer,
            "static_box": box,
            "lbl_source": lbl_source,
            "cb_source": cb_source,
            "source_options": [],
            "source_value": "",
            "lbl_model": lbl_model,
            "cb_model": cb_model,
            "lbl_pass": lbl_pass,
            "cb_pass": cb_pass,
            "lbl_keep": lbl_keep,
            "rename_container": rename_container,
            "rename_sizer": rename_sizer,
            "keep_controls": {}
        }
        self.steps.append(step_dict)
        
        # Initialize default selection
        if self.model_list:
            cb_model.SetSelection(0)
            self.on_step_model_change_by_step(step_dict)
            
        self.update_steps_visibility()
        
        # Update layout
        self.steps_sizer.Layout()
        self.panel_chain.Layout()
        self.Layout()
        
    def on_source_change_evt(self, event):
        cb = event.GetEventObject()
        for step_ui in self.steps:
            if step_ui.get("cb_source") == cb:
                sel = cb.GetSelection()
                opts = step_ui.get("source_options", [])
                if 0 <= sel < len(opts):
                    step_ui["source_value"] = opts[sel][1]
                break

    def update_all_source_choices(self):
        for i in range(1, len(self.steps)):
            self.update_source_choices_for_step(i)

    def update_source_choices_for_step(self, step_idx):
        step_ui = self.steps[step_idx]
        cb_source = step_ui.get("cb_source")
        if not cb_source:
            return

        current_val = step_ui.get("source_value", "")
        options = []
        none_label = self.i18n.tr("preset_pass_none")

        # 1. Default: pass stem of the immediately preceding step
        prev_step = self.steps[step_idx - 1]
        prev_pass = prev_step["cb_pass"].GetStringSelection()
        if prev_pass and prev_pass != none_label:
            disp = f"{self.i18n.tr('preset_source_step').format(num=step_idx, stem=prev_pass)} (default)"
            options.append((disp, f"step_{step_idx}:{prev_pass}"))

        # 2. Other stems from all previous steps (1 .. step_idx)
        for k in range(step_idx):
            st_ui = self.steps[k]
            mod = st_ui["cb_model"].GetStringSelection()
            stems = self.get_model_stems(mod) if mod else []
            for s in stems:
                code = f"step_{k+1}:{s}"
                if not any(c == code for _, c in options):
                    disp = self.i18n.tr("preset_source_step").format(num=k+1, stem=s)
                    options.append((disp, code))

        # 3. Original input audio
        options.append((self.i18n.tr("preset_source_original"), "input"))

        step_ui["source_options"] = options
        cb_source.Clear()
        for disp, _ in options:
            cb_source.Append(disp)

        matched_idx = 0
        if current_val:
            for idx, (_, code) in enumerate(options):
                if code == current_val:
                    matched_idx = idx
                    break
        cb_source.SetSelection(matched_idx)
        step_ui["source_value"] = options[matched_idx][1] if options else ""

    def on_step_model_change_evt(self, event):
        cb_model = event.GetEventObject()
        step_ui = None
        idx = -1
        for i, step in enumerate(self.steps):
            if step["cb_model"] == cb_model:
                step_ui = step
                idx = i
                break
        if not step_ui:
            return
            
        self.on_step_model_change_by_step(step_ui)
        
    def on_step_model_change_by_step(self, step_ui):
        cb_model = step_ui["cb_model"]
        cb_pass = step_ui["cb_pass"]
        
        model = cb_model.GetStringSelection()
        stems = self.get_model_stems(model)
        
        cb_pass.Clear()
        cb_pass.Append(self.i18n.tr("preset_pass_none"))
        for s in stems:
            cb_pass.Append(s)
            
        if stems:
            cb_pass.SetSelection(1) # Default to first real stem
        else:
            cb_pass.SetSelection(0)
            
        self.update_step_rename_fields(step_ui)
        self.update_all_source_choices()

    def on_pass_stem_change_evt(self, event):
        cb_pass = event.GetEventObject()
        step_ui = None
        for step in self.steps:
            if step["cb_pass"] == cb_pass:
                step_ui = step
                break
        if not step_ui:
            return
        self.on_pass_stem_change_by_step(step_ui)

    def on_pass_stem_change_by_step(self, step_ui):
        cb_pass = step_ui["cb_pass"]
        sel_idx = cb_pass.GetSelection()
        if sel_idx == wx.NOT_FOUND:
            return
            
        pass_stem = cb_pass.GetString(sel_idx)
        none_label = self.i18n.tr("preset_pass_none")
        if "keep_controls" in step_ui:
            for stem, (chk, txt) in step_ui["keep_controls"].items():
                is_pass = (pass_stem != none_label and stem == pass_stem)
                chk.SetValue(not is_pass)
                txt.Enable(not is_pass)
                
        self.update_all_source_choices()

    def update_step_rename_fields(self, step_ui):
        step_ui["rename_sizer"].Clear(True)
        step_ui["keep_controls"] = {}
        
        model = step_ui["cb_model"].GetStringSelection()
        stems = self.get_model_stems(model)
        
        grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=6)
        grid.AddGrowableCol(1, 1)
        
        pass_stem = step_ui["cb_pass"].GetString(step_ui["cb_pass"].GetSelection()) if step_ui["cb_pass"].GetSelection() != wx.NOT_FOUND else ""
        none_label = self.i18n.tr("preset_pass_none")
        
        for stem in stems:
            is_pass = (pass_stem != none_label and stem == pass_stem)
            
            chk = wx.CheckBox(step_ui["rename_container"], label=stem)
            chk.SetValue(not is_pass)
            
            txt = wx.TextCtrl(step_ui["rename_container"])
            txt.SetHint(f"e.g. _{stem.capitalize()}")
            txt.Enable(not is_pass)
            txt.SetName(self.i18n.tr("preset_suffix_accessible_name").format(stem=stem))
            
            chk.Bind(wx.EVT_CHECKBOX, lambda evt, c=chk, t=txt: t.Enable(c.GetValue()))
            
            grid.Add(chk, flag=wx.ALIGN_CENTER_VERTICAL)
            grid.Add(txt, flag=wx.EXPAND)
            
            step_ui["keep_controls"][stem] = (chk, txt)
            
        step_ui["rename_sizer"].Add(grid, flag=wx.EXPAND)
        step_ui["rename_container"].Layout()
        
        self.steps_container.Layout()
        self.panel_chain.Layout()
        self.Layout()
            
    def update_steps_visibility(self):
        for i, step_ui in enumerate(self.steps):
            is_last = (i == len(self.steps) - 1)
            step_ui["cb_pass"].Show(not is_last)
            step_ui["lbl_pass"].Show(not is_last)
            step_ui["lbl_keep"].Show(True)
            step_ui["rename_container"].Show(True)
            
            if is_last and "keep_controls" in step_ui:
                for stem, (chk, txt) in step_ui["keep_controls"].items():
                    chk.SetValue(True)
                    txt.Enable(True)
                    
        self.update_all_source_choices()

    def on_save(self, event):
        # 1. Validate name
        name = self.txt_name.GetValue().strip()
        if not name:
            wx.MessageBox(self.i18n.tr("preset_error_empty_name"), self.i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
            return
            
        preset_type = self.cb_type.GetSelection()
        config = {}
        
        if preset_type == 0:
            # --- Single Model ---
            model = self._resolve(self.cb_single_model.GetStringSelection())
            if not model:
                wx.MessageBox(self.i18n.tr("preset_error_no_model").format(num=1), self.i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
                return
                
            config["type"] = "single"
            config["model_1"] = model
            
            # Build rename map
            rename_map = {}
            for stem, field in self.single_rename_fields.items():
                val = field.GetValue().strip()
                if val:
                    # Ensure starts with underscore
                    if not val.startswith("_"):
                        val = f"_{val}"
                    rename_map[stem] = val
                    
            if rename_map:
                config["rename_map"] = rename_map
                
            if self.chk_mix.GetValue():
                mix_target = self.txt_mix_target.GetValue().strip()
                if mix_target:
                    if not mix_target.startswith("_"):
                        mix_target = f"_{mix_target}"
                    config["mix_remaining_to"] = mix_target
        else:
            # --- Chained Models ---
            config["type"] = "chain"
            none_label = self.i18n.tr("preset_pass_none")
            
            # We iterate steps
            for i, step_ui in enumerate(self.steps):
                step_idx = i + 1
                model = self._resolve(step_ui["cb_model"].GetStringSelection())
                if not model:
                    wx.MessageBox(self.i18n.tr("preset_error_no_model").format(num=step_idx), self.i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
                    return
                
                config[f"model_{step_idx}"] = model
                
                # Source audio for step >= 2
                if i > 0:
                    src_val = step_ui.get("source_value", "")
                    prev_pass_str = self.steps[i-1]["cb_pass"].GetStringSelection()
                    prev_default = f"step_{i}:{prev_pass_str}"
                    if src_val and src_val != prev_default:
                        config[f"m{step_idx}_source"] = src_val
                
                # Intermediate steps configuration (all steps except the last)
                if i < len(self.steps) - 1:
                    pass_stem = step_ui["cb_pass"].GetStringSelection()
                    if pass_stem and pass_stem != none_label:
                        pass_key = "pass_stem" if i == 0 else f"pass_stem_{step_idx}"
                        config[pass_key] = pass_stem
                
                # Rename map for this step
                rename_map = {}
                if "keep_controls" in step_ui:
                    for stem, (chk, txt) in step_ui["keep_controls"].items():
                        if chk.GetValue():
                            val = txt.GetValue().strip()
                            if val:
                                if not val.startswith("_"):
                                    val = f"_{val}"
                                rename_map[stem] = val
                            else:
                                rename_map[stem] = f"_{stem.capitalize()}"
                        else:
                            rename_map[stem] = None
                if rename_map:
                    config[f"m{step_idx}_rename_map"] = rename_map
                
        # Validate duplicate suffixes to prevent output collisions
        duplicate_suffixes = PresetManager.validate_preset_suffixes(config)
        if duplicate_suffixes:
            dups_str = ", ".join(duplicate_suffixes)
            warn_title = self.i18n.tr("msg_warning") or "Attenzione"
            warn_msg = self.i18n.tr("preset_warn_duplicate_suffixes", suffixes=dups_str)
            if not warn_msg or warn_msg == "preset_warn_duplicate_suffixes":
                warn_msg = f"Attenzione: il preset contiene suffissi di output duplicati ({dups_str}). Continuare comunque?"
            dlg = wx.MessageDialog(self, warn_msg, warn_title, wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
            res = dlg.ShowModal()
            dlg.Destroy()
            if res != wx.ID_YES:
                return

        # Save preset via manager
        self.preset_key = PresetManager.save_custom_preset(name, config)
        if not self.preset_key:
            # Writing to disk failed: keep the dialog open instead of pretending success.
            wx.MessageBox(
                self.i18n.tr("preset_save_failed"),
                self.i18n.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return
        self.EndModal(wx.ID_OK)
