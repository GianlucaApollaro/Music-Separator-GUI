import wx
import os
from gui.preset_manager import PresetManager
from gui.audio_utils import get_model_stems

class CustomPresetDialog(wx.Dialog):
    def __init__(self, parent, model_list, i18n):
        super().__init__(parent, title=i18n.tr("preset_create_title"), size=(550, 650),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.model_list = model_list
        self.i18n = i18n
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
        self.cb_single_model = wx.ComboBox(self.panel_single, style=wx.CB_DROPDOWN | wx.CB_READONLY)
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
        
        self.cb_single_model.Bind(wx.EVT_COMBOBOX, lambda evt: self.update_single_rename_fields())
        if self.model_list:
            self.cb_single_model.SetSelection(0)
            self.update_single_rename_fields()

    def update_single_rename_fields(self):
        # Clear previous fields and destroy windows
        self.single_rename_sizer.Clear(True)
        self.single_rename_fields = {}
        
        model = self.cb_single_model.GetValue()
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
        
        # Last Step Rename Map Section
        self.box_last_rename = wx.StaticBox(self.panel_chain, label=self.i18n.tr("preset_rename_title"))
        last_rename_sizer = wx.StaticBoxSizer(self.box_last_rename, wx.VERTICAL)
        
        self.chain_rename_container = wx.Panel(self.panel_chain)
        self.chain_rename_sizer = wx.BoxSizer(wx.VERTICAL)
        self.chain_rename_container.SetSizer(self.chain_rename_sizer)
        self.chain_rename_fields = {}
        
        last_rename_sizer.Add(self.chain_rename_container, flag=wx.EXPAND | wx.ALL, border=5)
        sizer.Add(last_rename_sizer, flag=wx.EXPAND)
        
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
        if len(self.steps) < 4:  # Max 4 steps
            self.add_chain_step_ui()
        
    def on_remove_step(self, event):
        if len(self.steps) > 2: # Keep at least 2 steps for a chain
            step_ui = self.steps.pop()
            
            # Destroy all windows/widgets associated with the step
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
            self.update_chain_rename_fields()
            self.steps_sizer.Layout()
            self.panel_chain.Layout()
            self.Layout()
            
    def add_chain_step_ui(self):
        step_num = len(self.steps) + 1
        
        box = wx.StaticBox(self.steps_container, label=self.i18n.tr("preset_step_title").format(num=step_num))
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        # Model selector
        lbl_model = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_model_select"))
        cb_model = wx.ComboBox(self.steps_container, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        cb_model.AppendItems(self.model_list)
        
        box_sizer.Add(lbl_model, flag=wx.TOP, border=2)
        box_sizer.Add(cb_model, flag=wx.EXPAND | wx.BOTTOM, border=8)
        
        # Intermediate settings (not needed on the very last step, but we define them and conditionally read them)
        lbl_pass = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_pass_stem"))
        cb_pass = wx.Choice(self.steps_container)
        
        lbl_keep = wx.StaticText(self.steps_container, label=self.i18n.tr("preset_keep_rename_title"))
        rename_container = wx.Panel(self.steps_container)
        rename_sizer = wx.BoxSizer(wx.VERTICAL)
        rename_container.SetSizer(rename_sizer)
        
        box_sizer.Add(lbl_pass, flag=wx.TOP, border=2)
        box_sizer.Add(cb_pass, flag=wx.EXPAND | wx.BOTTOM, border=8)
        box_sizer.Add(lbl_keep, flag=wx.TOP, border=2)
        box_sizer.Add(rename_container, flag=wx.EXPAND | wx.BOTTOM, border=5)
        
        self.steps_sizer.Add(box_sizer, flag=wx.EXPAND | wx.BOTTOM, border=10)
        
        cb_model.Bind(wx.EVT_COMBOBOX, self.on_step_model_change_evt)
        cb_pass.Bind(wx.EVT_CHOICE, self.on_pass_stem_change_evt)
        
        step_dict = {
            "box_sizer": box_sizer,
            "static_box": box,
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
        self.update_chain_rename_fields()
        
        # Update layout
        self.steps_sizer.Layout()
        self.panel_chain.Layout()
        self.Layout()
        
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
        
        # If this is the last step, update the final rename fields
        if idx == len(self.steps) - 1:
            self.update_chain_rename_fields()
            
    def on_step_model_change_by_step(self, step_ui):
        cb_model = step_ui["cb_model"]
        cb_pass = step_ui["cb_pass"]
        
        model = cb_model.GetValue()
        stems = self.get_model_stems(model)
        
        cb_pass.Clear()
        cb_pass.AppendItems(stems)
        if stems:
            cb_pass.SetSelection(0)
            
        self.update_step_rename_fields(step_ui)

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
        if "keep_controls" in step_ui:
            for stem, (chk, txt) in step_ui["keep_controls"].items():
                is_pass = (stem == pass_stem)
                chk.SetValue(not is_pass)
                txt.Enable(not is_pass)

    def update_step_rename_fields(self, step_ui):
        step_ui["rename_sizer"].Clear(True)
        step_ui["keep_controls"] = {}
        
        model = step_ui["cb_model"].GetValue()
        stems = self.get_model_stems(model)
        
        grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=6)
        grid.AddGrowableCol(1, 1)
        
        pass_stem = step_ui["cb_pass"].GetString(step_ui["cb_pass"].GetSelection()) if step_ui["cb_pass"].GetSelection() != wx.NOT_FOUND else ""
        
        for stem in stems:
            chk_label = self.i18n.tr("preset_keep_stem_label").format(stem=stem)
            chk = wx.CheckBox(step_ui["rename_container"], label=chk_label)
            
            is_pass = (stem == pass_stem)
            chk.SetValue(not is_pass)
            
            txt = wx.TextCtrl(step_ui["rename_container"])
            txt.SetHint(f"e.g. _{stem.capitalize()}")
            txt.SetValue(f"_{stem.capitalize()}")
            txt.SetName(self.i18n.tr("preset_suffix_accessible_name").format(stem=stem))
            txt.Enable(not is_pass)
            
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
            show_intermediate = not is_last
            step_ui["cb_pass"].Enable(show_intermediate)
            step_ui["lbl_pass"].Enable(show_intermediate)
            step_ui["lbl_keep"].Enable(show_intermediate)
            step_ui["rename_container"].Enable(show_intermediate)
            if show_intermediate:
                step_ui["lbl_keep"].Show()
                step_ui["rename_container"].Show()
                step_ui["lbl_pass"].Show()
                step_ui["cb_pass"].Show()
            else:
                step_ui["lbl_keep"].Hide()
                step_ui["rename_container"].Hide()
                step_ui["lbl_pass"].Hide()
                step_ui["cb_pass"].Hide()

    def update_chain_rename_fields(self):
        self.chain_rename_sizer.Clear(True)
        self.chain_rename_fields = {}
        
        if not self.steps:
            return
            
        last_step = self.steps[-1]
        model = last_step["cb_model"].GetValue()
        stems = self.get_model_stems(model)
        
        grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=8)
        grid.AddGrowableCol(1, 1)
        
        for stem in stems:
            lbl_stem = wx.StaticText(self.chain_rename_container, label=stem)
            txt_suffix = wx.TextCtrl(self.chain_rename_container)
            txt_suffix.SetHint(f"e.g. _{stem.capitalize()}")
            grid.Add(lbl_stem, flag=wx.ALIGN_CENTER_VERTICAL)
            grid.Add(txt_suffix, flag=wx.EXPAND)
            self.chain_rename_fields[stem] = txt_suffix
            
        self.chain_rename_sizer.Add(grid, flag=wx.EXPAND)
        self.chain_rename_container.Layout()
        self.panel_chain.Layout()
        self.Layout()



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
            model = self.cb_single_model.GetValue()
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
            
            # We iterate steps
            for i, step_ui in enumerate(self.steps):
                step_idx = i + 1
                model = step_ui["cb_model"].GetValue()
                if not model:
                    wx.MessageBox(self.i18n.tr("preset_error_no_model").format(num=step_idx), self.i18n.tr("msg_error_title"), wx.OK | wx.ICON_ERROR)
                    return
                
                config[f"model_{step_idx}"] = model
                
                # Intermediate steps configuration (all steps except the last)
                if i < len(self.steps) - 1:
                    pass_stem = step_ui["cb_pass"].GetString(step_ui["cb_pass"].GetSelection())
                    # intermediate pass keys: 'pass_stem' for model 1, 'pass_stem_2' for model 2, etc.
                    pass_key = "pass_stem" if i == 0 else f"pass_stem_{step_idx}"
                    config[pass_key] = pass_stem
                    
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
                                rename_map[stem] = None
                    if rename_map:
                        config[f"m{step_idx}_rename_map"] = rename_map
            
            # Rename map for the very last step in the chain
            last_idx = len(self.steps)
            rename_map = {}
            for stem, field in self.chain_rename_fields.items():
                val = field.GetValue().strip()
                if val:
                    if not val.startswith("_"):
                        val = f"_{val}"
                    rename_map[stem] = val
                    
            if rename_map:
                config[f"m{last_idx}_rename_map"] = rename_map
                
        # Save preset via manager
        self.preset_key = PresetManager.save_custom_preset(name, config)
        self.EndModal(wx.ID_OK)
