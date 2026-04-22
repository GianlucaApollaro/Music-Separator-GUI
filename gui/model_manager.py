import os
import json
import threading
import logging
from typing import Dict, Optional, List, Callable
from gui.utils import download_file
import wx

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or os.path.join(os.getcwd(), 'models')
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
                "htdemucs",
                "htdemucs_ft",
                "htdemucs_6s"
            ]
        }

        self._loading = True
        self._observers: List[Callable] = []

        threading.Thread(target=self._sync_models_json, daemon=True).start()

    def add_ready_callback(self, cb: Callable):
        if not self._loading:
            wx.CallAfter(cb)
        else:
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
            logger.error(f"Error parsing download_checks.json: {e}")

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

    def get_model_list(self) -> List[str]:
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

        if files_to_download:
            logger_callback(f"Checking models: {model_name}\n")
            for fname, url in files_to_download.items():
                dest_path = os.path.join(self.models_dir, fname)
                if not os.path.exists(dest_path):
                    logger_callback(f"Downloading {fname}...\n")
                    success = download_file(url, dest_path, progress_callback)
                    if success:
                        logger_callback(f"Downloaded {fname}\n")
                    else:
                        logger_callback(f"Failed to download {fname}\n")
                        return None
                else:
                    logger_callback(f"Found local: {fname}\n")
        return target_model_filename

    def _get_target_from_files(self, model_name: str, files_to_download: dict) -> str:
        demucs_names = ["htdemucs", "htdemucs_ft", "htdemucs_6s", "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"]
        if model_name in demucs_names or "htdemucs" in model_name or "Demucs" in model_name:
             for f in files_to_download.keys():
                 if f.endswith('.yaml'):
                     return f
        else:
             for f in files_to_download.keys():
                if any(f.endswith(ext) for ext in ['.ckpt', '.onnx', '.th', '.pth']):
                    return f
        return list(files_to_download.keys())[0] if files_to_download else model_name
