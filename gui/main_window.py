import wx
import os
import json
import threading
from gui.worker import SeparationThread, EVT_LOG_ID, EVT_DONE_ID, EVT_PROGRESS_ID
from gui.i18n_manager import i18n
from gui.utils import download_file

class MainWindow(wx.Frame):
    def __init__(self, parent, title):
        super(MainWindow, self).__init__(parent, title=i18n.tr("app_title"), size=(600, 600))
        
        self.worker = None
        self.downloadable_models = {} # Map FriendlyName -> { filename: url, ... }
        self.downloadable_aliases = {} # Map ShortName -> { filename: url, ... } (not displayed in UI)
        self.downloadable_models_by_file = {} # Map filename -> { filename: url, ... } (for reverse lookup if needed)
        
        self.preset_keys = [
            "preset_none", 
            "preset_vocal_split", 
            "preset_vocal_dereverb",
            "preset_ultimate_stems",
            "preset_ultimate_drums",
            "preset_chorus_hq",

            "preset_guitar_specialist",
            "preset_crowd_live",
            "preset_vocal_rvc",
        ]
        
        # Define preset configurations
        self.presets_config = {
            "preset_none": {},
            "preset_vocal_split": {
                "type": "chain",
                "model_1": "bs_roformer_karaoke_frazer_becruily.ckpt",
                "model_2": "mel_band_roformer_becruily_deux.ckpt",
                "pass_stem": "instrumental",
                "m1_keep_name": "_Lead",
                "m2_rename_map": {
                    "vocals": "_Backing",
                    "instrumental": "_Instrumental",
                    "other": "_Instrumental"
                }
            },
            "preset_vocal_dereverb": {
                "type": "chain",
                "model_1": "mel_band_roformer_becruily_deux.ckpt",
                "model_2": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
                "pass_stem": "vocals",
                "m1_keep_name": "_Instrumental",
                "m2_rename_map": {
                    "noreverb": "_DeReverb",
                    "reverb": "_Reverb"
                }
            },
            "preset_ultimate_stems": {
                "type": "chain",
                "model_1": "mel_band_roformer_becruily_deux.ckpt",
                "model_2": "BS-Roformer-SW.ckpt",
                "pass_stem": "instrumental",
                "m1_keep_name": "_Vocals",
                "m1_keep_pass_stem_name": "_Instrumental",
                "m2_rename_map": {
                    "drums": "_Drums",
                    "bass": "_Bass",
                    "piano": "_Piano",
                    "guitar": "_Guitar",
                    "other": "_Other",
                    "vocals": None  # Discard empty vocals extracted from instrumental
                }
            },
            "preset_chorus_hq": {
                "type": "chain",
                "model_1": "mel_band_roformer_kim_ft_unwa.ckpt",
                "model_2": "bs_roformer_male_female_by_aufr33_sdr_7.2889.ckpt",
                "pass_stem": "vocals",
                "m1_keep_name": "_Instrumental",
                "m2_rename_map": {
                    "vocals": "_Female",
                    "other": "_Male",
                    "instrumental": "_Male",
                    "male": "_Male",
                    "female": "_Female"
                }
            },
            "preset_ultimate_drums": {
                "type": "chain",
                "model_1": "mel_band_roformer_becruily_deux.ckpt",
                "model_2": "BS-Roformer-SW.ckpt",
                "model_3": "MDX23C-DrumSep-aufr33-jarredou.ckpt",
                "pass_stem": "instrumental",
                "pass_stem_2": "drums",
                "m1_keep_name": "_Vocals",
                "m2_keep_pass_stem_name": "_Drums_Stereo", # Keep the stereo drums too
                "m2_rename_map": {
                    "bass": "_Bass",
                    "piano": "_Piano",
                    "guitar": "_Guitar",
                    "other": "_Other",
                    "drums": "_Drums_Stereo",
                    "vocals": None  # Discard empty vocals extracted from instrumental
                },
                "m3_rename_map": {
                    "kick": "_Kick",
                    "snare": "_Snare",
                    "hi-hat": "_Hi-Hat",
                    "cymbals": "_Cymbals",
                    "tom-toms": "_Toms",
                    "other": "_Drums_Other"
                }
            },

            "preset_guitar_specialist": {
                "name": "Guitar Extraction (3 Stems)",
                "type": "chain",
                "model_1": "mel_band_roformer_becruily_deux.ckpt",
                "model_2": "mel_band_roformer_guitar_becruily.ckpt",
                "pass_stem": "instrumental",
                "m1_keep_name": "_Vocals",
                "m2_rename_map": {
                    "guitar": "_Guitar",
                    "other": "_Other",
                    "no guitar": "_Other"
                }
            },
            "preset_crowd_live": {
                "type": "chain",
                "model_1": "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
                "model_2": "mel_band_roformer_becruily_deux.ckpt",
                "pass_stem": "other",
                "m1_keep_name": "_Crowd",
                "m2_rename_map": {
                    "vocals": "_Lead",
                    "instrumental": "_Instrumental",
                    "other": "_Instrumental"
                }
            },
            "preset_vocal_rvc": {
                "type": "chain",
                "model_1": "mel_band_roformer_karaoke_becruily.ckpt",
                "model_2": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
                "pass_stem": "vocals",
                "m1_keep_name": "_Instrumental_BVs",
                "m2_rename_map": {
                    "noreverb": "_Lead_Clean",
                    "reverb": "_Lead_Reverb"
                }
            },
        }
        

        self.LoadDownloadChecks()

        self.InitUI()
        self.InitMenu()
        self.Centre()
        
        # Bind Custom Events
        self.Connect(-1, -1, EVT_LOG_ID, self.OnLog)
        self.Connect(-1, -1, EVT_DONE_ID, self.OnDone)
        self.Connect(-1, -1, EVT_PROGRESS_ID, self.OnProgress)

    def LoadDownloadChecks(self):
        """Parses download_checks.json for advanced models with URLs."""
        model_dir = os.path.join(os.getcwd(), 'models')
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)

        json_path = os.path.join(model_dir, 'download_checks.json')
        
        # Try to sync the latest download_checks.json from TRvlvr repo
        remote_json_url = "https://raw.githubusercontent.com/TRvlvr/application_data/main/filelists/download_checks.json"
        try:
            # Sync without progress bar for silence at startup
            download_file(remote_json_url, json_path, overwrite=True)
            print("Successfully synced model download list from server.")
        except Exception as e:
            print(f"Skipping model list sync (offline or server error): {e}")

        if not os.path.exists(json_path):
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Repository prefixes
            PUBLIC_REPO = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models"
            VIP_REPO = "https://github.com/Anjok0109/ai_magic/releases/download/v5"
            CONFIG_BASE = "https://raw.githubusercontent.com/TRvlvr/application_data/main/mdx_model_data/mdx_c_configs"

            # Expand target lists.
            target_lists = [
                'roformer_download_list', 'mdx23c_download_list', 'mdx23_download_list', 
                'mdx23c_download_vip_list', 'mdx_download_list', 'mdx_download_vip_list', 
                'vr_download_list', 'demucs_download_list', 'other_network_list', 'other_network_list_new'
            ]
            
            for list_name in target_lists:
                if list_name in data:
                    is_vip = "vip" in list_name.lower()
                    repo_prefix = VIP_REPO if is_vip else PUBLIC_REPO
                    
                    for name, file_info in data[list_name].items():
                        normalized_info = {}
                        if isinstance(file_info, str):
                            normalized_info[file_info] = f"{repo_prefix}/{file_info}"
                        elif isinstance(file_info, dict):
                            for fname, val in file_info.items():
                                if val.startswith("http"):
                                    normalized_info[fname] = val
                                else:
                                    normalized_info[fname] = f"{repo_prefix}/{fname}"
                                    normalized_info[val] = f"{CONFIG_BASE}/{val}"
                        
                        if normalized_info:
                            self.downloadable_models[name] = normalized_info
                            for fname in normalized_info.keys():
                                if any(fname.endswith(ext) for ext in ['.ckpt', '.onnx', '.th', '.pth']):
                                    self.downloadable_models_by_file[fname] = normalized_info

            # --- MANUALLY INJECT OUR CUSTOM MODELS FOR GUI DISPLAY/DOWNLOAD ---
            # These are required so the GUI knows how to download them with a progress bar.
            
            # 1. Becruily Deux - Match library expectations
            becruily_deux_info = {
                "mel_band_roformer_becruily_deux.ckpt": "https://huggingface.co/becruily/mel-band-roformer-deux/resolve/main/becruily_deux.ckpt",
                "config_deux_becruily.yaml": "https://huggingface.co/becruily/mel-band-roformer-deux/resolve/main/config_deux_becruily.yaml"
            }
            self.downloadable_models["Roformer Model: MelBand Roformer Deux | (by becruily)"] = becruily_deux_info
            self.downloadable_models_by_file["mel_band_roformer_becruily_deux.ckpt"] = becruily_deux_info

            # 2. Becruily Karaoke
            becruily_kara_info = {
                "mel_band_roformer_karaoke_becruily.ckpt": "https://huggingface.co/becruily/mel-band-roformer-karaoke/resolve/main/mel_band_roformer_karaoke_becruily.ckpt",
                "config_mel_band_roformer_karaoke_becruily.yaml": "https://huggingface.co/becruily/mel-band-roformer-karaoke/resolve/main/config_karaoke_becruily.yaml"
            }
            self.downloadable_models_by_file["mel_band_roformer_karaoke_becruily.ckpt"] = becruily_kara_info

            # 3. Becruily Guitar
            becruily_guitar_info = {
                "mel_band_roformer_guitar_becruily.ckpt": "https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/becruily_guitar.ckpt",
                "mel_band_roformer_guitar_becruily.yaml": "https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/config_guitar_becruily.yaml"
            }
            self.downloadable_models_by_file["mel_band_roformer_guitar_becruily.ckpt"] = becruily_guitar_info

            # 4. BS-Roformer Karaoke (Frazer)
            frazer_kara_info = {
                "bs_roformer_karaoke_frazer_becruily.ckpt": "https://huggingface.co/becruily/bs-roformer-karaoke/resolve/main/bs_roformer_karaoke_frazer_becruily.ckpt",
                "bs_roformer_karaoke_frazer_becruily.yaml": "https://huggingface.co/becruily/bs-roformer-karaoke/resolve/main/config_karaoke_frazer_becruily.yaml"
            }
            self.downloadable_models_by_file["bs_roformer_karaoke_frazer_becruily.ckpt"] = frazer_kara_info

            # 5. Crowd Roformer Fix
            crowd_info = {
                "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt": "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.4/mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
                "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144_config.yaml": "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.4/model_mel_band_roformer_crowd.yaml"
            }
            self.downloadable_models_by_file["mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"] = crowd_info

            # 6. MDX23C DrumSep
            drumsep_info = {
                "MDX23C-DrumSep-aufr33-jarredou.ckpt": "https://huggingface.co/Politrees/UVR_resources/resolve/main/models/MDX23C/MDX23C-DrumSep-aufr33-jarredou.ckpt",
                "MDX23C-DrumSep-aufr33-jarredou.yaml": "https://huggingface.co/Politrees/UVR_resources/resolve/main/models/MDX23C/config_drumsep_mdx23c.yaml"
            }
            self.downloadable_models_by_file["MDX23C-DrumSep-aufr33-jarredou.ckpt"] = drumsep_info
            
        except Exception as e:
            print(f"Error parsing download_checks.json: {e}")
                                
        except Exception as e:
            print(f"Error parsing download_checks.json: {e}")

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
        vbox.Add(hbox1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Output Dir ---
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.st2 = wx.StaticText(self.panel, label=i18n.tr("output_dir"))
        hbox2.Add(self.st2, flag=wx.RIGHT, border=15) # align with above
        self.tc_output = wx.TextCtrl(self.panel)
        # Default to a folder next to executable
        self.tc_output.SetValue(os.path.join(os.getcwd(), 'output'))
        hbox2.Add(self.tc_output, proportion=1)
        self.btn_output = wx.Button(self.panel, label=i18n.tr("browse"))
        self.btn_output.Bind(wx.EVT_BUTTON, self.OnBrowseOutput)
        hbox2.Add(self.btn_output, flag=wx.LEFT, border=5)
        vbox.Add(hbox2, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Model Selection ---
        hbox3 = wx.BoxSizer(wx.HORIZONTAL)
        self.st3 = wx.StaticText(self.panel, label=i18n.tr("model"))
        hbox3.Add(self.st3, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=25)
        
        # Categorized Models
        self.models_dict = {
            "Favorites": [
                "BS-Roformer-SW.ckpt",
                "UVR-MDX-NET-Inst_HQ_5.onnx",
                "mel_band_roformer_kim_ft_unwa.ckpt",
                "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
            ],
            "Becruily & RoFormer Specific (User Req)": [
                "mel_band_roformer_becruily_deux.ckpt",
                "bs_roformer_karaoke_frazer_becruily.ckpt",
                "mel_band_roformer_guitar_becruily.ckpt",
                "mel_band_roformer_karaoke_becruily.ckpt",
                "mel_band_roformer_vocals_becruily.ckpt",
                "mel_band_roformer_instrumental_becruily.ckpt",
                "mel_band_roformer_denoise_debleed_gabox.ckpt"
            ],
            "De-Reverb / De-Echo": [
                "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
                "dereverb_mel_band_roformer_less_aggressive_anvuew_sdr_18.8050.ckpt",
                "dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt",
                "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt"
            ],
            "Voice Gender Split (Male/Female)": [
                "bs_roformer_male_female_by_aufr33_sdr_7.2889.ckpt",
                "model_chorus_bs_roformer_ep_267_sdr_24.1275.ckpt"
            ],
            "Karaoke / Backing Vocals": [
                "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
            ],
            "Crowd / Applause Extraction": [
                "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
                "UVR-MDX-NET_Crowd_HQ_1.onnx"
            ],
            "Drum Separation": [
                "MDX23C-DrumSep-aufr33-jarredou.ckpt"
            ],
            "Aspiration / Breath Elements": [
                "aspiration_mel_band_roformer_sdr_18.9845.ckpt"
            ],
            "Denoise": [
                "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt"
            ],
            "Demucs v4 (Multi-Stem)": [
                "htdemucs",
                "htdemucs_ft",
                "htdemucs_6s"
            ]
        }
        
        # Add imported models to the dictionary if they are not already there
        if self.downloadable_models:
             self.models_dict["From download_checks.json"] = list(self.downloadable_models.keys())

        # Flatten for ComboBox but keep order
        self.model_list = []
        for category, mods in self.models_dict.items():
            for m in mods:
                self.model_list.append(m)

        self.cb_model = wx.ComboBox(self.panel, choices=self.model_list, style=wx.CB_DROPDOWN)
        self.cb_model.SetValue(self.model_list[0]) # Default
        self.cb_model.SetToolTip("Select a model or type a custom model filename (e.g. from download_checks.json)")
        hbox3.Add(self.cb_model, proportion=1, flag=wx.EXPAND)
        vbox.Add(hbox3, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Ensemble Option ---
        hbox_ens_chk = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_ensemble = wx.CheckBox(self.panel, label=i18n.tr("enable_ensemble"))
        self.chk_ensemble.SetValue(False)
        self.chk_ensemble.Bind(wx.EVT_CHECKBOX, self.OnEnsembleCheck)
        hbox_ens_chk.Add(self.chk_ensemble, flag=wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(hbox_ens_chk, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Secondary Model (Ensemble) ---
        hbox_ens_mod = wx.BoxSizer(wx.HORIZONTAL)
        self.st_model_2 = wx.StaticText(self.panel, label=i18n.tr("secondary_model"))
        hbox_ens_mod.Add(self.st_model_2, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.cb_model_2 = wx.ComboBox(self.panel, choices=self.model_list, style=wx.CB_DROPDOWN)
        if len(self.model_list) > 1:
            self.cb_model_2.SetValue(self.model_list[1])
        else:
            self.cb_model_2.SetValue(self.model_list[0])
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
        for key in self.preset_keys:
            self.cb_preset.Append(i18n.tr(key))
        self.cb_preset.SetSelection(0)
        self.cb_preset.Bind(wx.EVT_COMBOBOX, self.OnPresetChange)
        self.hbox_preset.Add(self.cb_preset, proportion=1, flag=wx.EXPAND)
        vbox.Add(self.hbox_preset, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Options ---
        hbox4 = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_gpu = wx.CheckBox(self.panel, label=i18n.tr("use_gpu"))
        
        # Check if CUDA is actually available (e.g., this is not the CPU-only build)
        import torch
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            self.chk_gpu.SetValue(True)
        else:
            self.chk_gpu.SetValue(False)
            self.chk_gpu.Disable()
            self.chk_gpu.SetToolTip("GPU (CUDA) is not available in this build.")
            
        hbox4.Add(self.chk_gpu)

        self.chk_remove_numbers = wx.CheckBox(self.panel, label=i18n.tr("remove_leading_numbers"))
        self.chk_remove_numbers.SetValue(False)
        hbox4.Add(self.chk_remove_numbers, flag=wx.LEFT, border=15)
        
        hbox4.AddStretchSpacer(prop=1)
        self.st_format = wx.StaticText(self.panel, label=i18n.tr("output_format"))
        hbox4.Add(self.st_format, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.cb_format = wx.ComboBox(self.panel, choices=['WAV', 'FLAC', 'MP3'], style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.cb_format.SetValue('WAV')
        hbox4.Add(self.cb_format)

        vbox.Add(hbox4, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        # --- Chunk Duration ---
        self.chunk_values = [60, 120, 300, 600, 900, 1200]
        self.chunk_choices = ["1 min", "2 min", "5 min", "10 min", "15 min", "20 min"]
        hbox_chunk = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_chunk = wx.CheckBox(self.panel, label=i18n.tr("chunk_enable"))
        self.chk_chunk.SetValue(False)
        self.chk_chunk.Bind(wx.EVT_CHECKBOX, self.OnChunkCheck)
        hbox_chunk.Add(self.chk_chunk, flag=wx.ALIGN_CENTER_VERTICAL)
        hbox_chunk.AddStretchSpacer(prop=1)
        self.st_chunk_dur = wx.StaticText(self.panel, label=i18n.tr("chunk_duration_label"))
        self.st_chunk_dur.Disable()
        hbox_chunk.Add(self.st_chunk_dur, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=8)
        self.cb_chunk = wx.ComboBox(self.panel, choices=self.chunk_choices, style=wx.CB_DROPDOWN | wx.CB_READONLY, size=(90, -1))
        self.cb_chunk.SetSelection(0)  # Default: 1 min
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
        preset_key = self.preset_keys[idx]
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
        
        self.st_preset.SetLabel(i18n.tr("preset_label"))
        old_sel = self.cb_preset.GetSelection()
        if old_sel == wx.NOT_FOUND:
            old_sel = 0
        self.cb_preset.Clear()
        for key in self.preset_keys:
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
        with wx.FileDialog(self, "Open Audio file(s)", wildcard="Audio files (*.mp3;*.wav;*.flac;*.m4a)|*.mp3;*.wav;*.flac;*.m4a",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            paths = fileDialog.GetPaths()
            self.tc_input.SetValue("|".join(paths))

    def OnBrowseOutput(self, event):
        with wx.DirDialog(self, "Choose Output Directory",
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
            wx.MessageBox(i18n.tr("msg_success"), "Success", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox(i18n.tr("msg_error"), "Error", wx.OK | wx.ICON_ERROR)

    def DownloadWithProgress(self, url, dest):
        """Helper to download with UI updates for log."""
        def progress(current, total):
            if total > 0:
                percent = int((current / total) * 100)
                self.gauge.SetValue(percent)
                wx.YieldIfNeeded() # Process events and repaint the UI to prevent freeze
        return download_file(url, dest, progress)

    def _resolve_and_download_model(self, model_name):
        files_to_download = {}
        target_model_filename = model_name
        
        # Repository prefixes for fallback
        PUBLIC_REPO = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models"
        CONFIG_BASE = "https://raw.githubusercontent.com/TRvlvr/application_data/main/mdx_model_data/mdx_c_configs"

        if model_name in self.downloadable_models:
            files_to_download = self.downloadable_models[model_name]
        elif model_name in self.downloadable_aliases:
            files_to_download = self.downloadable_aliases[model_name]
            # Handle demucs/aliases logic...
            demucs_names = ["htdemucs", "htdemucs_ft", "htdemucs_6s", "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"]
            if model_name in demucs_names or "htdemucs" in model_name:
                 for f in files_to_download.keys():
                     if f.endswith('.yaml'):
                         target_model_filename = f
                         break
            else:
                 for f in files_to_download.keys():
                    if any(f.endswith(ext) for ext in ['.ckpt', '.onnx', '.th', '.pth']):
                        target_model_filename = f
                        break
        elif model_name in self.downloadable_models_by_file:
             files_to_download = self.downloadable_models_by_file[model_name]
             target_model_filename = model_name

        if files_to_download:
            self.tc_log.AppendText(i18n.tr("status_checking_models", model=model_name) + "\n")
            model_dir = os.path.join(os.getcwd(), 'models')
            if not os.path.exists(model_dir):
                os.makedirs(model_dir)

            for fname, url in files_to_download.items():
                dest_path = os.path.join(model_dir, fname)
                if not os.path.exists(dest_path):
                    self.tc_log.AppendText(i18n.tr("status_downloading", file=fname) + "\n")
                    success = self.DownloadWithProgress(url, dest_path)
                    if success:
                        self.tc_log.AppendText(i18n.tr("status_downloaded", file=fname) + "\n")
                    else:
                        # If download failed, log and stop (critical for registered items)
                        self.tc_log.AppendText(i18n.tr("status_download_failed", file=fname) + "\n")
                        return None
                else:
                    self.tc_log.AppendText(i18n.tr("status_found_local", file=fname) + "\n")
        return target_model_filename

    def OnStart(self, event):
        input_string = self.tc_input.GetValue()
        output_dir = self.tc_output.GetValue().strip().strip('"')
        model_name = self.cb_model.GetValue()

        if not input_string:
            wx.MessageBox(i18n.tr("msg_select_input"), "Error", wx.OK | wx.ICON_ERROR)
            return
            
        input_files = [p.strip().strip('"') for p in input_string.split("|") if os.path.exists(p.strip().strip('"'))]
        if not input_files:
            wx.MessageBox(i18n.tr("msg_select_input"), "Error", wx.OK | wx.ICON_ERROR)
            return

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError:
                wx.MessageBox(i18n.tr("msg_create_output_err"), "Error", wx.OK | wx.ICON_ERROR)
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
            preset_key = self.preset_keys[preset_idx]
            preset_config = self.presets_config[preset_key]

        out_format = self.cb_format.GetValue()

        if preset_config:
            # Resolve and download both models for the preset
            target_model_filename = self._resolve_and_download_model(preset_config["model_1"])
            if not target_model_filename:
                self.btn_start.Enable()
                self.btn_stop.Disable()
                return

            target_model_filename_2 = self._resolve_and_download_model(preset_config["model_2"])
            if not target_model_filename_2:
                self.btn_start.Enable()
                self.btn_stop.Disable()
                return

            target_model_filename_3 = None
            if "model_3" in preset_config:
                target_model_filename_3 = self._resolve_and_download_model(preset_config["model_3"])
                if not target_model_filename_3:
                    self.btn_start.Enable()
                    self.btn_stop.Disable()
                    return

            self.worker = SeparationThread(self, input_files, output_dir, target_model_filename, self.chk_gpu.GetValue(), out_format, target_model_filename_2, target_model_filename_3, preset_config, chunk_duration=chunk_duration, remove_leading_numbers=self.chk_remove_numbers.GetValue())
            self.worker.start()
            return
            
        # Context for standard or parallel ensemble separation
        target_model_filename = self._resolve_and_download_model(model_name)
        if not target_model_filename:
            self.btn_start.Enable()
            self.btn_stop.Disable()
            return
            
        target_model_filename_2 = None
        ensemble_algorithm = "avg_wave"
        if self.chk_ensemble.GetValue():
            model_name_2 = self.cb_model_2.GetValue()
            target_model_filename_2 = self._resolve_and_download_model(model_name_2)
            if not target_model_filename_2:
                self.btn_start.Enable()
                self.btn_stop.Disable()
                return
            ensemble_algorithm = self.cb_ens_algo.GetValue()

        self.worker = SeparationThread(self, input_files, output_dir, target_model_filename, self.chk_gpu.GetValue(), out_format, target_model_filename_2, ensemble_algorithm=ensemble_algorithm, chunk_duration=chunk_duration, remove_leading_numbers=self.chk_remove_numbers.GetValue())
        self.worker.start()

    def OnStop(self, event):
        if self.worker:
            self.worker.stop()
            self.tc_log.AppendText(i18n.tr("msg_stopping") + "\n")
