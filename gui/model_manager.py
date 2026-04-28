import os
import json
import threading
import logging
from typing import Dict, Optional, List, Callable
from gui.utils import download_file, get_app_data_dir
import wx

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or os.path.join(get_app_data_dir(), 'models')
        os.makedirs(self.models_dir, exist_ok=True)

        self.downloadable_models: Dict[str, Dict[str, str]] = {}
        self.downloadable_models_by_file: Dict[str, Dict[str, str]] = {}
        self.downloadable_aliases: Dict[str, Dict[str, str]] = {}
        
        self.models_dict: Dict[str, List[str]] = {
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
                "htdemucs.yaml",
                "htdemucs_ft.yaml",
                "htdemucs_6s.yaml",
                "hdemucs_mmi.yaml"
            ],
            "GaboxR67 Custom Models": [
                "inst_gaboxFlowersV10.ckpt",
                "Inst_Fv8.ckpt",
                "Lead_VocalDereverb.ckpt",
                "last_bs_roformer.ckpt"
            ],
            "Unwa Custom Models (High Quality)": [
                "bs_large_v2_inst.ckpt",
                "bs_roformer_inst_hyperacev2.ckpt",
                "bs_roformer_voc_hyperacev2.ckpt",
                "BS-Roformer-Resurrection.ckpt",
                "BS-Roformer-Resurrection-Inst.ckpt",
                "big_beta7.ckpt",
                "bs_roformer_revive.ckpt",
                "bs_roformer_revive2.ckpt",
                "bs_roformer_revive3e.ckpt",
                "melband_roformer_instvoc_duality_v1.ckpt",
                "melband_roformer_instvox_duality_v2.ckpt",
                "bs_roformer_fno.ckpt",
                "kimmel_unwa_ft.ckpt",
                "kimmel_unwa_ft2.ckpt",
                "kimmel_unwa_ft2_bleedless.ckpt",
                "kimmel_unwa_ft3_prev.ckpt"
            ],
            "Dereverb / Echo Models (by Sucial)": [
                "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
                "dereverb_echo_mbr_v2_sdr_dry_13.4843.ckpt",
            ],
            "Multi-Stem Models": [
                "bs_roformer_multistem.safetensors",
            ]
        }

        self._loading = True
        self._ready_event = threading.Event()
        self._observers: List[Callable] = []

        threading.Thread(target=self._sync_models_json, daemon=True).start()

    def add_ready_callback(self, cb: Callable):
        if not self._ready_event.is_set():
            # Wait for ready signal if not set yet
            threading.Thread(target=lambda: (self._ready_event.wait(), wx.CallAfter(cb)), daemon=True).start()
        else:
            wx.CallAfter(cb)
            self._observers.append(cb)

    def _sync_models_json(self):
        json_path = os.path.join(self.models_dir, 'download_checks.json')
        url = "https://raw.githubusercontent.com/TRvlvr/application_data/main/filelists/download_checks.json"
        
        try:
            download_file(url, json_path, overwrite=True, timeout=(5, 15))
        except Exception as e:
            logger.warning(f"Skipping model list sync: {e}")
            
        if os.path.exists(json_path):
            self._parse_models_json(json_path)

        # Add downloaded models to dictionary
        if self.downloadable_models:
             self.models_dict["From download_checks.json"] = list(self.downloadable_models.keys())

        self._loading = False
        for cb in self._observers:
            wx.CallAfter(cb)

    def _parse_models_json(self, json_path: str):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            PUBLIC_REPO = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models"
            VIP_REPO = "https://github.com/Anjok0109/ai_magic/releases/download/v5"
            CONFIG_BASE = "https://raw.githubusercontent.com/TRvlvr/application_data/main/mdx_model_data/mdx_c_configs"

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
                                if not isinstance(val, str):
                                    # Valore non-stringa (es. ID numerico): costruisci solo l'URL del modello
                                    normalized_info[fname] = f"{repo_prefix}/{fname}"
                                elif val.startswith("http"):
                                    normalized_info[fname] = val
                                else:
                                    normalized_info[fname] = f"{repo_prefix}/{fname}"
                                    if '.' in val:
                                        normalized_info[val] = f"{CONFIG_BASE}/{val}"
                        
                        if normalized_info:
                            self.downloadable_models[name] = normalized_info
                            for fname in normalized_info.keys():
                                if any(fname.endswith(ext) for ext in ['.ckpt', '.onnx', '.th', '.pth']):
                                    self.downloadable_models_by_file[fname] = normalized_info

            self._inject_custom_models()
        except Exception as e:
            logger.error(f"Error syncing models: {e}")
        finally:
            self._loading = False
            self._ready_event.set()

    def _inject_custom_models(self):
        becruily_deux_info = {
            "mel_band_roformer_becruily_deux.ckpt": "https://huggingface.co/becruily/mel-band-roformer-deux/resolve/main/becruily_deux.ckpt",
            "config_deux_becruily.yaml": "https://huggingface.co/becruily/mel-band-roformer-deux/resolve/main/config_deux_becruily.yaml"
        }
        self.downloadable_models["Roformer Model: MelBand Roformer Deux | (by becruily)"] = becruily_deux_info
        self.downloadable_models_by_file["mel_band_roformer_becruily_deux.ckpt"] = becruily_deux_info

        becruily_kara_info = {
            "mel_band_roformer_karaoke_becruily.ckpt": "https://huggingface.co/becruily/mel-band-roformer-karaoke/resolve/main/mel_band_roformer_karaoke_becruily.ckpt",
            "config_mel_band_roformer_karaoke_becruily.yaml": "https://huggingface.co/becruily/mel-band-roformer-karaoke/resolve/main/config_karaoke_becruily.yaml"
        }
        self.downloadable_models_by_file["mel_band_roformer_karaoke_becruily.ckpt"] = becruily_kara_info

        becruily_guitar_info = {
            "mel_band_roformer_guitar_becruily.ckpt": "https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/becruily_guitar.ckpt",
            "mel_band_roformer_guitar_becruily.yaml": "https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/config_guitar_becruily.yaml"
        }
        self.downloadable_models_by_file["mel_band_roformer_guitar_becruily.ckpt"] = becruily_guitar_info

        frazer_kara_info = {
            "bs_roformer_karaoke_frazer_becruily.ckpt": "https://huggingface.co/becruily/bs-roformer-karaoke/resolve/main/bs_roformer_karaoke_frazer_becruily.ckpt",
            "bs_roformer_karaoke_frazer_becruily.yaml": "https://huggingface.co/becruily/bs-roformer-karaoke/resolve/main/config_karaoke_frazer_becruily.yaml"
        }
        self.downloadable_models_by_file["bs_roformer_karaoke_frazer_becruily.ckpt"] = frazer_kara_info

        crowd_info = {
            "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt": "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.4/mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
            "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144_config.yaml": "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.4/model_mel_band_roformer_crowd.yaml"
        }
        self.downloadable_models_by_file["mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt"] = crowd_info

        drumsep_info = {
            "MDX23C-DrumSep-aufr33-jarredou.ckpt": "https://huggingface.co/Politrees/UVR_resources/resolve/main/models/MDX23C/MDX23C-DrumSep-aufr33-jarredou.ckpt",
            "config_drumsep_mdx23c.yaml": "https://huggingface.co/Politrees/UVR_resources/resolve/main/models/MDX23C/config_drumsep_mdx23c.yaml"
        }
        self.downloadable_models_by_file["MDX23C-DrumSep-aufr33-jarredou.ckpt"] = drumsep_info

        gabox_v10_info = {
            "inst_gaboxFlowersV10.ckpt": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/melbandroformers/instrumental/inst_gaboxFlowersV10.ckpt",
            "inst_gaboxFlowersV10.yaml": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/melbandroformers/instrumental/v10.yaml"
        }
        self.downloadable_models["Roformer Model: Gabox Instrumental V10"] = gabox_v10_info
        self.downloadable_models_by_file["inst_gaboxFlowersV10.ckpt"] = gabox_v10_info

        gabox_fv8_info = {
            "Inst_Fv8.ckpt": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/melbandroformers/experimental/Inst_Fv8.ckpt",
            "Inst_Fv8.yaml": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/melbandroformers/instrumental/v10.yaml"
        }
        self.downloadable_models["Roformer Model: Gabox Experimental Inst_Fv8"] = gabox_fv8_info
        self.downloadable_models_by_file["Inst_Fv8.ckpt"] = gabox_fv8_info

        gabox_dereverb_info = {
            "Lead_VocalDereverb.ckpt": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/melbandroformers/experimental/Lead_VocalDereverb.ckpt",
            "Lead_VocalDereverb.yaml": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/melbandroformers/instrumental/v10.yaml"
        }
        self.downloadable_models["Roformer Model: Lead Vocal Dereverb | (by GaboxR67)"] = gabox_dereverb_info
        self.downloadable_models_by_file["Lead_VocalDereverb.ckpt"] = gabox_dereverb_info

        gabox_last_bs_info = {
            "last_bs_roformer.ckpt": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/bsroformers/last_bs_roformer.ckpt",
            "last_bs_roformer.yaml": "https://huggingface.co/GaboxR67/MelBandRoformers/resolve/main/bsroformers/karaoke_bs_roformer.yaml"
        }
        self.downloadable_models["Roformer Model: Last BS Roformer | (by GaboxR67)"] = gabox_last_bs_info
        self.downloadable_models_by_file["last_bs_roformer.ckpt"] = gabox_last_bs_info

        # pcunwa models
        unwa_large_inst_info = {
            "bs_large_v2_inst.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Large-Inst/resolve/main/bs_large_v2_inst.ckpt",
            "bs_large_v2_inst.yaml": "https://huggingface.co/pcunwa/BS-Roformer-Large-Inst/resolve/main/config.yaml"
        }
        self.downloadable_models_by_file["bs_large_v2_inst.ckpt"] = unwa_large_inst_info

        unwa_hyperace_inst_info = {
            "bs_roformer_inst_hyperacev2.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-HyperACE/resolve/main/v2_inst/bs_roformer_inst_hyperacev2.ckpt",
            "bs_roformer_inst_hyperacev2.yaml": "https://huggingface.co/pcunwa/BS-Roformer-HyperACE/resolve/main/v2_inst/config.yaml"
        }
        self.downloadable_models_by_file["bs_roformer_inst_hyperacev2.ckpt"] = unwa_hyperace_inst_info

        unwa_hyperace_voc_info = {
            "bs_roformer_voc_hyperacev2.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-HyperACE/resolve/main/v2_voc/bs_roformer_voc_hyperacev2.ckpt",
            "bs_roformer_voc_hyperacev2.yaml": "https://huggingface.co/pcunwa/BS-Roformer-HyperACE/resolve/main/v2_voc/config.yaml"
        }
        self.downloadable_models_by_file["bs_roformer_voc_hyperacev2.ckpt"] = unwa_hyperace_voc_info

        unwa_resurrection_info = {
            "BS-Roformer-Resurrection.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Resurrection/resolve/main/BS-Roformer-Resurrection.ckpt",
            "BS-Roformer-Resurrection.yaml": "https://huggingface.co/pcunwa/BS-Roformer-Resurrection/resolve/main/BS-Roformer-Resurrection-Config.yaml"
        }
        self.downloadable_models_by_file["BS-Roformer-Resurrection.ckpt"] = unwa_resurrection_info

        unwa_resurrection_inst_info = {
            "BS-Roformer-Resurrection-Inst.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Resurrection/resolve/main/BS-Roformer-Resurrection-Inst.ckpt",
            "BS-Roformer-Resurrection-Inst.yaml": "https://huggingface.co/pcunwa/BS-Roformer-Resurrection/resolve/main/BS-Roformer-Resurrection-Inst-Config.yaml"
        }
        self.downloadable_models_by_file["BS-Roformer-Resurrection-Inst.ckpt"] = unwa_resurrection_inst_info

        unwa_big_beta7_info = {
            "big_beta7.ckpt": "https://huggingface.co/pcunwa/Mel-Band-Roformer-big/resolve/main/big_beta7.ckpt",
            "big_beta7.yaml": "https://huggingface.co/pcunwa/Mel-Band-Roformer-big/resolve/main/big_beta7.yaml"
        }
        self.downloadable_models_by_file["big_beta7.ckpt"] = unwa_big_beta7_info

        unwa_revive_info = {
            "bs_roformer_revive.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Revive/resolve/main/bs_roformer_revive.ckpt",
            "bs_roformer_revive2.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Revive/resolve/main/bs_roformer_revive2.ckpt",
            "bs_roformer_revive3e.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Revive/resolve/main/bs_roformer_revive3e.ckpt",
            "bs_roformer_revive.yaml": "https://huggingface.co/pcunwa/BS-Roformer-Revive/resolve/main/config.yaml"
        }
        self.downloadable_models_by_file["bs_roformer_revive.ckpt"] = unwa_revive_info
        self.downloadable_models_by_file["bs_roformer_revive2.ckpt"] = unwa_revive_info
        self.downloadable_models_by_file["bs_roformer_revive3e.ckpt"] = unwa_revive_info

        unwa_duality_info = {
            "melband_roformer_instvoc_duality_v1.ckpt": "https://huggingface.co/pcunwa/Mel-Band-Roformer-InstVoc-Duality/resolve/main/melband_roformer_instvoc_duality_v1.ckpt",
            "melband_roformer_instvox_duality_v2.ckpt": "https://huggingface.co/pcunwa/Mel-Band-Roformer-InstVoc-Duality/resolve/main/melband_roformer_instvox_duality_v2.ckpt",
            "melband_roformer_instvoc_duality.yaml": "https://huggingface.co/pcunwa/Mel-Band-Roformer-InstVoc-Duality/resolve/main/config_melbandroformer_instvoc_duality.yaml"
        }
        self.downloadable_models_by_file["melband_roformer_instvoc_duality_v1.ckpt"] = unwa_duality_info
        self.downloadable_models_by_file["melband_roformer_instvox_duality_v2.ckpt"] = unwa_duality_info

        unwa_fno_info = {
            "bs_roformer_fno.ckpt": "https://huggingface.co/pcunwa/BS-Roformer-Inst-FNO/resolve/main/bs_roformer_fno.ckpt",
            "bs_roformer_fno.yaml": "https://huggingface.co/pcunwa/BS-Roformer-Inst-FNO/resolve/main/bsrofo_fno.yaml"
        }
        self.downloadable_models_by_file["bs_roformer_fno.ckpt"] = unwa_fno_info

        # All kimmel variants share the same config YAML (config_kimmel_unwa_ft.yaml)
        _kimmel_yaml = "config_kimmel_unwa_ft.yaml"
        _kimmel_yaml_url = "https://huggingface.co/pcunwa/Kim-Mel-Band-Roformer-FT/resolve/main/config_kimmel_unwa_ft.yaml"
        _kimmel_base = "https://huggingface.co/pcunwa/Kim-Mel-Band-Roformer-FT/resolve/main/"
        
        for _fname in ["kimmel_unwa_ft.ckpt", "kimmel_unwa_ft2.ckpt", "kimmel_unwa_ft2_bleedless.ckpt", "kimmel_unwa_ft3_prev.ckpt"]:
            self.downloadable_models_by_file[_fname] = {
                _fname: _kimmel_base + _fname,
                _kimmel_yaml: _kimmel_yaml_url,
            }

        # Sucial Dereverb/Echo models (MelBandRoformer, standard architecture)
        _sucial_base = "https://huggingface.co/Sucial/Dereverb-Echo_Mel_Band_Roformer/resolve/main/"
        # v1: large model (836 MB), 2 stems (dry + other)
        dereverb_v1_info = {
            "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt": _sucial_base + "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
            "config_dereverb-echo_mel_band_roformer.yaml": _sucial_base + "config_dereverb-echo_mel_band_roformer.yaml",
        }
        self.downloadable_models_by_file["dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt"] = dereverb_v1_info

        # v2: lighter model (456 MB), 1 stem (dry only, SDR 13.48)
        dereverb_v2_info = {
            "dereverb_echo_mbr_v2_sdr_dry_13.4843.ckpt": _sucial_base + "dereverb_echo_mbr_v2_sdr_dry_13.4843.ckpt",
            "config_dereverb_echo_mbr_v2.yaml": _sucial_base + "config_dereverb_echo_mbr_v2.yaml",
        }
        self.downloadable_models_by_file["dereverb_echo_mbr_v2_sdr_dry_13.4843.ckpt"] = dereverb_v2_info

        # AEmotionStudio BS-Roformer Multistem (4 stems: drums, bass, other, vocals)
        # Uses .safetensors format — handled by the patched loader in worker.py
        _aemotion_base = "https://huggingface.co/AEmotionStudio/roformer-models/resolve/main/bs_roformer/multistem/"
        multistem_info = {
            "bs_roformer_multistem.safetensors": _aemotion_base + "model.safetensors",
            "bs_roformer_multistem_config.yaml": _aemotion_base + "config.yaml",
        }
        self.downloadable_models_by_file["bs_roformer_multistem.safetensors"] = multistem_info

        # Demucs aliases to help resolve and download
        self.downloadable_aliases["htdemucs"] = {"htdemucs.yaml": ""}
        self.downloadable_aliases["htdemucs_ft"] = {"htdemucs_ft.yaml": ""}
        self.downloadable_aliases["htdemucs_6s"] = {"htdemucs_6s.yaml": ""}
        self.downloadable_aliases["hdemucs_mmi"] = {"hdemucs_mmi.yaml": ""}

    def get_model_list(self) -> List[str]:
        """Wait up to 5 seconds for the model catalog to be ready."""
        if not self._ready_event.wait(timeout=5.0):
            logger.warning("Model catalog not ready yet, returning partial list.")
            
        model_list = []
        for category, mods in self.models_dict.items():
            for m in mods:
                model_list.append(m)
        return model_list

    def resolve_and_download(self, model_name: str, logger_callback: Callable[[str], None], progress_callback: Callable[[float, float], None]) -> Optional[str]:
        files_to_download = {}
        target_model_filename = model_name

        if model_name in self.downloadable_models:
            files_to_download = self.downloadable_models[model_name]
            target_model_filename = self._get_target_from_files(model_name, files_to_download)
        elif model_name in self.downloadable_aliases:
            files_to_download = self.downloadable_aliases[model_name]
            target_model_filename = self._get_target_from_files(model_name, files_to_download)
        elif model_name in self.downloadable_models_by_file:
            files_to_download = self.downloadable_models_by_file[model_name]
            target_model_filename = model_name
        
        if not files_to_download:
            # Maybe it's a built-in model that requires no download and we haven't mapped it yet
            return model_name

        downloaded_files = []
        try:
            logger_callback(f"Checking models: {model_name}\n")
            for fname, url in files_to_download.items():
                dest_path = os.path.join(self.models_dir, fname)
                if not os.path.exists(dest_path):
                    logger_callback(f"Downloading {fname}...\n")
                    if not download_file(url, dest_path, progress_callback, timeout=(15, 60)):
                        raise Exception(f"Failed to download {fname}")
                    downloaded_files.append(dest_path)
                    logger_callback(f"Downloaded {fname}\n")
                else:
                    logger_callback(f"Found local: {fname}\n")
                
                if dest_path.endswith('.yaml'):
                    self._patch_yaml_config(dest_path)

            return target_model_filename
        except Exception as e:
            # Cleanup partially downloaded files
            for f in downloaded_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except Exception:
                    pass
            logger_callback(f"Download failed: {e}\n")
            return None

    def _patch_yaml_config(self, yaml_path: str):
        """Fixes common compatibility issues in custom YAML configs for python-audio-separator."""
        basename = os.path.basename(yaml_path)
        # Whitelist of models to patch
        unwa_yamls = [
            "bs_large_v2_inst.yaml", "bs_roformer_inst_hyperacev2.yaml", "bs_roformer_voc_hyperacev2.yaml",
            "BS-Roformer-Resurrection.yaml", "BS-Roformer-Resurrection-Inst.yaml", "big_beta7.yaml",
            "bs_roformer_revive.yaml", "melband_roformer_instvoc_duality.yaml", "bs_roformer_fno.yaml",
            "config_kimmel_unwa_ft.yaml",
            "config_dereverb-echo_mel_band_roformer.yaml", "config_dereverb_echo_mbr_v2.yaml",
            "bs_roformer_multistem_config.yaml",
        ]
        if basename not in ["inst_gaboxFlowersV10.yaml", "Inst_Fv8.yaml", "Lead_VocalDereverb.yaml", "last_bs_roformer.yaml"] + unwa_yamls:
            return

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            changed = False
            
            # Force audio-separator to recognize this as a Roformer
            if "is_roformer:" not in content:
                content = "is_roformer: true\n" + content
                changed = True

            # Explicitly declare model architecture so roformer_loader doesn't guess
            if "model_type:" not in content:
                # If it's the last_bs_roformer, it's a BS Roformer, otherwise it's MelBand
                is_bs = any(x in basename for x in ["last_bs_roformer", "bs_large", "hyperace", "Resurrection", "revive", "fno"])
                mtype = "bs_roformer" if is_bs else "mel_band_roformer"
                content = f"model_type: {mtype}\n" + content
                changed = True
                
            # Experimental models (Inst_Fv8, Dereverb) use dim: 384 and depth: 6, unlike v10 which uses 256/12
            if basename in ["Inst_Fv8.yaml", "Lead_VocalDereverb.yaml"]:
                if "  dim: 256" in content:
                    content = content.replace("  dim: 256", "  dim: 384")
                    changed = True
                if "  depth: 12" in content:
                    content = content.replace("  depth: 12", "  depth: 6")
                    changed = True
                
            # Revert any broken num_subbands/norm/act replacements from previous faulty runs
            if "  norm: Identity" in content:
                content = content.replace("  norm: Identity\n  act: GELU\n", "")
                changed = True
            if "  num_subbands:" in content:
                content = content.replace("  num_subbands:", "  num_bands:")
                changed = True

            if changed:
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Patched compatibility issues in {yaml_path}")
        except Exception as e:
            logger.warning(f"Failed to patch YAML {yaml_path}: {e}")

    def _get_target_from_files(self, model_name: str, files_to_download: dict) -> str:
        demucs_names = ["htdemucs", "htdemucs_ft", "htdemucs_6s", "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"]
        is_demucs = (model_name in demucs_names or 
                     "htdemucs" in model_name or 
                     "Demucs" in model_name or
                     any('demucs' in f.lower() for f in files_to_download.keys()))
        
        if is_demucs:
            # Search for .th file (model weights)
            for f in files_to_download.keys():
                if f.endswith('.th'):
                    return f
            # Or .yaml if no .th is explicitly in download_files
            for f in files_to_download.keys():
                if f.endswith('.yaml'):
                    return f
        else:
            for f in files_to_download.keys():
                if any(f.endswith(ext) for ext in ['.ckpt', '.onnx', '.pth', '.safetensors']):
                    return f
        return list(files_to_download.keys())[0] if files_to_download else model_name
