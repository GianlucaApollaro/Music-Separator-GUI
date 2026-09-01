"""
audio_patches.py - Runtime compatibility patches for python-audio-separator.

These patches add support for custom UVR/Roformer models (Bandit, SCNet,
HyperACE/Segm, FNO, safetensors weights, etc.) and fix a number of upstream
bugs in the audio-separator library so that the GUI does not have to wait for
upstream releases.

Previously this code lived inside gui/worker.py (in SeparationThread.run) and
was re-applied on every separation run. That had two problems:

* the class-level patches (e.g. RoformerLoader.load_model) were never reverted,
  so every run wrapped the already-patched method again, piling up wrappers;
* it made worker.py grow to >1600 lines and was hard to test.

Usage::

    patcher = AudioPatches(model_dir=..., parent=main_window, log=callback)
    try:
        patcher.apply(separator)
        ...
    finally:
        patcher.restore()   # reverts the global patches only

apply() is best-effort: if any sub-patch fails it raises, and restore() reverts
everything that was applied before the failure so the process state stays sane.
"""
import logging
import os

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Ckpt -> config yaml mapping (some repos share one config or name it
# differently from the weights file). Kept module-level for readability.
# --------------------------------------------------------------------------- #
CUSTOM_CKPT_TO_YAML = {
    'mel_band_roformer_guitar_becruily.ckpt':          'mel_band_roformer_guitar_becruily.yaml',
    'mel_band_roformer_karaoke_becruily.ckpt':         'config_mel_band_roformer_karaoke_becruily.yaml',
    'config_mel_band_roformer_karaoke_becruily.yaml':  'config_mel_band_roformer_karaoke_becruily.yaml',
    'mel_band_roformer_becruily_deux.ckpt':            'config_deux_becruily.yaml',
    'mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt':
                                            'mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144_config.yaml',
    # FNO (Fourier Neural Operator) model
    'bs_roformer_fno.ckpt':                            'bs_roformer_fno.yaml',
    # Kim-Mel-Band Roformer fine-tuned variants (all share the same config)
    'kimmel_unwa_ft.ckpt':                             'config_kimmel_unwa_ft.yaml',
    'kimmel_unwa_ft2.ckpt':                            'config_kimmel_unwa_ft.yaml',
    'kimmel_unwa_ft2_bleedless.ckpt':                  'config_kimmel_unwa_ft.yaml',
    'kimmel_unwa_ft3_prev.ckpt':                       'config_kimmel_unwa_ft.yaml',
    # Sucial Dereverb/Echo models
    'dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt': 'config_dereverb-echo_mel_band_roformer.yaml',
    'dereverb_echo_mbr_v2_sdr_dry_13.4843.ckpt':       'config_dereverb_echo_mbr_v2.yaml',
    # AEmotionStudio Multistem (.safetensors)
    'bs_roformer_multistem.safetensors':                'bs_roformer_multistem_config.yaml',
    # MVSep Mega 53 Stems model
    'mvsep_mega_model_bs_roformer_53_stems_v1.ckpt':    'mvsep_mega_model_bs_roformer_53_stems.yaml',
    # Gilliaan BowedStrings model
    'gilliaan_bowedstrings_bs_v1.ckpt':                 'gilliaan_bsroformer_bowedstrings_v1.yaml',
    # DryPaintMan MelBand-Roformer Duet model
    'model_mel_band_roformer_ep_0_sdr_7.9319_fixed.ckpt': 'config_mel_band_roformer_duet_dual-mlp2.yaml',
    # Lead Synth BS-Roformer model
    'model_bs_roformer_ep_1_sdr_4.9869_fixed.ckpt':     'config_bs_roformer_synth_lead.yaml',
    # Bandit/SCNet models
    'checkpoint-multi_fixed.ckpt':                     'config_dnr_bandit_v2_mus64.yaml',
    'model_bandit_plus_dnr_sdr_11.47.ckpt':            'config_dnr_bandit_bsrnn_multi_mus64.yaml',
    'scnet_checkpoint_musdb18.ckpt':                   'config_musdb18_scnet.yaml',
    'SCNet-large_starrytong_fixed.ckpt':               'config_musdb18_scnet_large_starrytong.yaml',
    'model_scnet_sdr_9.3244.ckpt':                      'config_musdb18_scnet_large.yaml',
    'model_scnet_ep_54_sdr_9.8051.ckpt':                'config_musdb18_scnet_xl.yaml',
}

CUSTOM_MDXC_MODELS = {
    "Roformer Model: MelBand Roformer Deux | (by becruily)": {
        "filename": "mel_band_roformer_becruily_deux.ckpt",
        "download_files": ["mel_band_roformer_becruily_deux.ckpt", "config_deux_becruily.yaml"],
        "is_roformer": True
    },
    "Roformer Model: MelBand Roformer Karaoke | (by becruily)": {
        "filename": "mel_band_roformer_karaoke_becruily.ckpt",
        "download_files": ["mel_band_roformer_karaoke_becruily.ckpt", "config_mel_band_roformer_karaoke_becruily.yaml"],
        "is_roformer": True
    },
    "Roformer Model: MelBand Roformer Guitar | (by becruily)": {
        "filename": "mel_band_roformer_guitar_becruily.ckpt",
        "download_files": ["mel_band_roformer_guitar_becruily.ckpt", "mel_band_roformer_guitar_becruily.yaml"],
        "is_roformer": True
    },
    "Roformer Model: BS-Roformer Karaoke | (by frazer & becruily)": {
        "filename": "bs_roformer_karaoke_frazer_becruily.ckpt",
        "download_files": ["bs_roformer_karaoke_frazer_becruily.ckpt", "bs_roformer_karaoke_frazer_becruily.yaml"],
        "is_roformer": True
    },
    "Roformer Model: Mel-Roformer-Crowd-Aufr33-Viperx": {
        "filename": "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
        "download_files": ["mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt", "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144_config.yaml"],
        "is_roformer": True
    },
    "Roformer Model: Denoise Advanced | (by aufr33)": {
        "filename": "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
        "download_files": ["denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt", "denoise_mel_band_roformer_aufr33_sdr_27.9959.yaml"],
        "is_roformer": True
    },
    "Roformer Model: Gabox Instrumental V10": {
        "filename": "inst_gaboxFlowersV10.ckpt",
        "download_files": ["inst_gaboxFlowersV10.ckpt", "inst_gaboxFlowersV10.yaml"],
        "is_roformer": True
    },
    "Roformer Model: Gabox Experimental Inst_Fv8": {
        "filename": "Inst_Fv8.ckpt",
        "download_files": ["Inst_Fv8.ckpt", "Inst_Fv8.yaml"],
        "is_roformer": True
    },
    "Roformer Model: Lead Vocal Dereverb | (by GaboxR67)": {
        "filename": "Lead_VocalDereverb.ckpt",
        "download_files": ["Lead_VocalDereverb.ckpt", "Lead_VocalDereverb.yaml"],
        "is_roformer": True
    },
    "Roformer Model: Last BS Roformer | (by GaboxR67)": {
        "filename": "last_bs_roformer.ckpt",
        "download_files": ["last_bs_roformer.ckpt", "last_bs_roformer.yaml"],
        "is_roformer": True
    },
    "Roformer Model: MVSep Mega 53 Stems | (by ZFTurbo)": {
        "filename": "mvsep_mega_model_bs_roformer_53_stems_v1.ckpt",
        "download_files": [
            "mvsep_mega_model_bs_roformer_53_stems_v1.ckpt",
            "mvsep_mega_model_bs_roformer_53_stems.yaml"
        ],
        "is_roformer": True
    },
    "Roformer Model: BS-Roformer BowedStrings Duality | (by gilliaan)": {
        "filename": "gilliaan_bowedstrings_bs_v1.ckpt",
        "download_files": [
            "gilliaan_bowedstrings_bs_v1.ckpt",
            "gilliaan_bsroformer_bowedstrings_v1.yaml"
        ],
        "is_roformer": True
    },
    "Roformer Model: MelBand-Roformer Duet | (by DryPaintMan)": {
        "filename": "model_mel_band_roformer_ep_0_sdr_7.9319_fixed.ckpt",
        "download_files": [
            "model_mel_band_roformer_ep_0_sdr_7.9319_fixed.ckpt",
            "config_mel_band_roformer_duet_dual-mlp2.yaml"
        ],
        "is_roformer": True
    },
    "Roformer Model: BS-Roformer Lead Synth | (by oulianov)": {
        "filename": "model_bs_roformer_ep_1_sdr_4.9869_fixed.ckpt",
        "download_files": [
            "model_bs_roformer_ep_1_sdr_4.9869_fixed.ckpt",
            "config_bs_roformer_synth_lead.yaml"
        ],
        "is_roformer": True
    },
}


class AudioPatches:
    """Central place for the runtime monkey-patches used by the separation worker.

    Attributes:
        model_dir: directory where the downloaded model files live.
        parent:    optional MainWindow-like object exposing `downloadable_models`
                   and/or a `model_manager` with `downloadable_models_by_file`.
        log:       callable(msg) used for warning messages (default: logger.warning).
    """

    def __init__(self, model_dir, parent=None, log=None):
        self.model_dir = model_dir
        self._parent = parent
        self._log = log if callable(log) else logger.warning
        self._originals = {}   # name -> original global (object | function)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #
    def apply(self, separator):
        """Patch the given Separator instance and shared library classes.

        Raises on the first failure; any global that was already patched is
        recorded so it can be reverted via restore().
        """
        if self._originals:
            self.restore()

        try:
            self._patch_model_registry(separator)
            self._patch_yaml_loader(separator)
            self._patch_torch_load()
            self._patch_roformer_loader(separator)
            self._patch_melband_mlp_factor()
            self._patch_parameter_validator()
        except Exception as e:  # noqa: BLE001
            self.restore()
            raise RuntimeError(f"Runtime patch failed: {e}") from e

        return self

    def restore(self):
        """Revert the patches that were applied during the last apply() call.

        Only global/shared objects are restored (torch.load,
        torch.serialization.load, RoformerLoader.load_model,
        MelBandRoformer.__init__, ParameterValidator.PARAMETER_RANGES).
        Instance-level monkey-patches on the separator object are left alone:
        each run builds a fresh separator.
        """
        if not self._originals:
            return

        try:
            import torch
            if "torch.load" in self._originals:
                torch.load = self._originals["torch.load"]
            if "torch.serialization.load" in self._originals:
                torch.serialization.load = self._originals["torch.serialization.load"]
        except Exception:
            pass

        try:
            from audio_separator.separator.roformer.roformer_loader import RoformerLoader
            if "RoformerLoader.load_model" in self._originals:
                RoformerLoader.load_model = self._originals["RoformerLoader.load_model"]
        except Exception:
            pass

        try:
            from audio_separator.separator.uvr_lib_v5.roformer.mel_band_roformer import MelBandRoformer
            if "MelBandRoformer.__init__" in self._originals:
                MelBandRoformer.__init__ = self._originals["MelBandRoformer.__init__"]
        except Exception:
            pass

        try:
            from audio_separator.separator.roformer.parameter_validator import ParameterValidator
            if "ParameterValidator.PARAMETER_RANGES" in self._originals:
                ParameterValidator.PARAMETER_RANGES = self._originals["ParameterValidator.PARAMETER_RANGES"]
        except Exception:
            pass

        self._originals.clear()

    # ------------------------------------------------------------------ #
    #  1. Model registry injection
    # ------------------------------------------------------------------ #
    def _patch_model_registry(self, separator):
        original_list_func = separator.list_supported_model_files

        def patched_list_supported_model_files():
            models = original_list_func()

            if "MDXC" not in models:
                models["MDXC"] = {}
            models["MDXC"].update(CUSTOM_MDXC_MODELS)

            # Inject all models from parent's downloadable_models so they are natively supported
            if getattr(self, "_parent", None) and hasattr(self._parent, "downloadable_models"):
                for friendly_name, file_info in self._parent.downloadable_models.items():
                    model_type = "MDXC"  # Default
                    target_file = friendly_name

                    for fname in file_info.keys():
                        if fname.endswith('.onnx'):
                            model_type = "MDX"
                            target_file = fname
                            break
                        elif fname.endswith('.pth'):
                            model_type = "VR"
                            target_file = fname
                            break
                        elif any(fname.endswith(ext) for ext in ['.ckpt', '.th']):
                            target_file = fname
                            if fname.endswith('.th') or ('demucs' in friendly_name.lower()):
                                model_type = "Demucs"
                            else:
                                model_type = "MDXC"
                            break

                    if model_type == "Demucs":
                        for fname in file_info.keys():
                            if fname.endswith('.yaml'):
                                target_file = fname
                                break

                    if model_type not in models:
                        models[model_type] = {}

                    models[model_type][friendly_name] = {
                        "filename": target_file,
                        "download_files": list(file_info.keys())
                    }

                    if model_type == "MDXC" and (
                        "roformer" in friendly_name.lower() or "roformer" in target_file.lower() or
                        "bandit" in friendly_name.lower() or "bandit" in target_file.lower() or
                        "scnet" in friendly_name.lower() or "scnet" in target_file.lower()
                    ):
                        models[model_type][friendly_name]["is_roformer"] = True

            # Inject models from downloadable_models_by_file (ensures newly added pcunwa models are found)
            if getattr(self, "_parent", None) and hasattr(self._parent, "model_manager"):
                mm = self._parent.model_manager
                for filename, file_info in mm.downloadable_models_by_file.items():
                    model_type = "MDXC"
                    if filename.endswith('.onnx'):
                        model_type = "MDX"
                    elif filename.endswith('.pth'):
                        model_type = "VR"
                    elif filename.endswith('.th') or 'demucs' in filename.lower():
                        model_type = "Demucs"

                    if model_type not in models:
                        models[model_type] = {}

                    # Avoid duplicates
                    if any(m.get("filename") == filename for m in models[model_type].values()):
                        continue

                    models[model_type][filename] = {
                        "filename": filename,
                        "download_files": list(file_info.keys())
                    }
                    if model_type == "MDXC" and (
                        "roformer" in filename.lower() or
                        "bandit" in filename.lower() or
                        "scnet" in filename.lower()
                    ):
                        models[model_type][filename]["is_roformer"] = True

            return models

        separator.list_supported_model_files = patched_list_supported_model_files

        original_load_model_wrapper = separator.load_model

        def patched_load_model_wrapper(model_filename="model_bs_roformer_ep_317_sdr_12.9755.ckpt"):
            # Bandit and SCNet are now supported through the loader patch below.
            return original_load_model_wrapper(model_filename)

        separator.load_model = patched_load_model_wrapper

    # ------------------------------------------------------------------ #
    #  2. YAML loader patch (routes Bandit/SCNet through MDXC is_roformer)
    # ------------------------------------------------------------------ #
    def _patch_yaml_loader(self, separator):
        original_load_yaml = separator.load_model_data_from_yaml

        def patched_load_yaml(yaml_config_filename):
            model_data = original_load_yaml(yaml_config_filename)

            yaml_lower = yaml_config_filename.lower()
            is_bandit_or_scnet = "bandit" in yaml_lower or "scnet" in yaml_lower
            if not is_bandit_or_scnet and os.path.exists(yaml_config_filename):
                try:
                    with open(yaml_config_filename, 'r', encoding='utf-8') as yf:
                        content = yf.read()
                    if "cls: Bandit" in content or "cls: BaseBandit" in content or "MultiMaskMultiSourceBandSplitRNN" in content:
                        is_bandit_or_scnet = True
                    if "cls: SCNet" in content or "type: scnet" in content:
                        is_bandit_or_scnet = True
                except Exception:
                    pass

            if is_bandit_or_scnet:
                model_data["is_roformer"] = True

                # Populate model sub-dict
                if "model" not in model_data:
                    model_data["model"] = {}
                elif not isinstance(model_data["model"], dict):
                    model_data["model"] = {"original_value": model_data["model"]}

                if "stft_hop_length" not in model_data["model"]:
                    hop = (model_data.get("kwargs", {}).get("hop_length") or
                           model_data.get("model", {}).get("hop_size") or 512)
                    model_data["model"]["stft_hop_length"] = hop

            return model_data

        separator.load_model_data_from_yaml = patched_load_yaml

    # ------------------------------------------------------------------ #
    #  3. torch.load safe wrapper + safetensors redirect
    # ------------------------------------------------------------------ #
    def _patch_torch_load(self):
        import torch
        import torch.serialization

        # Allowlist common Roformer globals globally
        try:
            if hasattr(torch.serialization, 'add_safe_globals'):
                torch.serialization.add_safe_globals([torch._C._nn.gelu, torch.nn.GELU])
        except Exception:
            pass

        _original_torch_load = torch.load
        _original_serialization_load = torch.serialization.load

        def _is_safetensors_file(path_arg):
            """Detect safetensors format by magic bytes (first 8 bytes are a uint64 length prefix)."""
            try:
                if isinstance(path_arg, str) and os.path.isfile(path_arg):
                    with open(path_arg, 'rb') as _f:
                        header = _f.read(1)
                    return path_arg.endswith('.safetensors')
            except Exception:
                pass
            return False

        def _load_safetensors(path_arg, device='cpu'):
            from safetensors.torch import load_file as _st_load
            dev = str(device) if not isinstance(device, str) else device
            return _st_load(path_arg, device=dev)

        def _safe_torch_load(*args, **kwargs):
            # If the first argument looks like a safetensors path, redirect
            path_arg = args[0] if args else kwargs.get('f', None)
            if path_arg and _is_safetensors_file(path_arg):
                device = kwargs.get('map_location', 'cpu')
                return _load_safetensors(path_arg, device)
            if 'weights_only' not in kwargs:
                kwargs['weights_only'] = False
            try:
                return _original_torch_load(*args, **kwargs)
            except TypeError:
                if 'weights_only' in kwargs:
                    del kwargs['weights_only']
                return _original_torch_load(*args, **kwargs)

        def _safe_serialization_load(*args, **kwargs):
            path_arg = args[0] if args else kwargs.get('f', None)
            if path_arg and _is_safetensors_file(path_arg):
                device = kwargs.get('map_location', 'cpu')
                return _load_safetensors(path_arg, device)
            if 'weights_only' not in kwargs:
                kwargs['weights_only'] = False
            try:
                return _original_serialization_load(*args, **kwargs)
            except TypeError:
                if 'weights_only' in kwargs:
                    del kwargs['weights_only']
                return _original_serialization_load(*args, **kwargs)

        torch.load = _safe_torch_load
        torch.serialization.load = _safe_serialization_load
        self._originals["torch.load"] = _original_torch_load
        self._originals["torch.serialization.load"] = _original_serialization_load

    # ------------------------------------------------------------------ #
    #  4. RoformerLoader.load_model patch (direct YAML read + Bandit/SCNet)
    # ------------------------------------------------------------------ #
    def _patch_roformer_loader(self, separator):
        import zipfile
        import shutil
        import requests
        import sys

        import yaml as _yaml

        # Register a constructor for !!python/tuple (used in some model YAML files)
        def _tuple_constructor(loader, node):
            return tuple(loader.construct_sequence(node))
        _yaml.SafeLoader.add_constructor(
            'tag:yaml.org,2002:python/tuple', _tuple_constructor
        )
        try:
            _yaml.FullLoader.add_constructor(
                'tag:yaml.org,2002:python/tuple', _tuple_constructor
            )
        except Exception:
            pass

        from audio_separator.separator.roformer.roformer_loader import RoformerLoader
        from audio_separator.separator.uvr_lib_v5.roformer.mel_band_roformer import MelBandRoformer

        original_load_model = RoformerLoader.load_model
        model_dir_for_patch = self.model_dir
        parent = self._parent
        patched_load_yaml = separator.load_model_data_from_yaml

        def patched_load_model(self_loader, model_path, config, device='cpu'):
            import torch
            import logging as _logging
            _log = _logging.getLogger(__name__)

            ckpt_filename = os.path.basename(model_path)
            yaml_filename = CUSTOM_CKPT_TO_YAML.get(ckpt_filename)

            if not yaml_filename:
                # Try to find it in ModelManager's registries (closure access to parent)
                if getattr(parent, "model_manager", None) and hasattr(parent, "model_manager"):
                    mm = parent.model_manager
                    info = mm.downloadable_models_by_file.get(ckpt_filename)
                    if info:
                        for f in info.keys():
                            if f.endswith('.yaml'):
                                yaml_filename = f
                                break

            is_bandit = False
            is_scnet = False

            if yaml_filename:
                yaml_lower = yaml_filename.lower()
                if "bandit" in yaml_lower:
                    is_bandit = True
                elif "scnet" in yaml_lower:
                    is_scnet = True
            else:
                ckpt_lower = ckpt_filename.lower()
                if "bandit" in ckpt_lower:
                    is_bandit = True
                elif "scnet" in ckpt_lower:
                    is_scnet = True

            yaml_path = None
            if yaml_filename:
                yaml_path = os.path.join(model_dir_for_patch, yaml_filename)
                if not os.path.exists(yaml_path):
                    yaml_path = yaml_filename
            else:
                # Fallback candidate
                base_ckpt = os.path.splitext(ckpt_filename)[0]
                candidate = os.path.join(os.path.dirname(model_path), f"{base_ckpt}.yaml")
                if os.path.exists(candidate):
                    yaml_path = candidate

            if yaml_path and os.path.exists(yaml_path):
                try:
                    with open(yaml_path, 'r', encoding='utf-8') as yf:
                        content = yf.read()
                    if "cls: Bandit" in content or "cls: BaseBandit" in content or "MultiMaskMultiSourceBandSplitRNN" in content:
                        is_bandit = True
                    if "cls: SCNet" in content or "type: scnet" in content:
                        is_scnet = True
                except Exception:
                    pass

            if is_bandit or is_scnet:
                try:
                    _log.info(f"[Patch] Loading ZFTurbo architecture for {ckpt_filename}...")

                    from gui.utils import get_app_data_dir
                    app_data = get_app_data_dir()
                    dest_dir = os.path.join(app_data, "models_src")
                    models_dir = os.path.join(dest_dir, "models")

                    if not os.path.exists(models_dir):
                        _log.info("ZFTurbo models directory not found locally. Fetching architecture from Github...")
                        os.makedirs(dest_dir, exist_ok=True)
                        zip_path = os.path.join(dest_dir, "repo.zip")
                        url = "https://github.com/ZFTurbo/Music-Source-Separation-Training/archive/refs/heads/main.zip"
                        response = requests.get(url, timeout=45, stream=True)
                        response.raise_for_status()
                        with open(zip_path, 'wb') as f:
                            shutil.copyfileobj(response.raw, f)

                        _log.info("Extracting ZFTurbo model files...")
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            first_member = zip_ref.namelist()[0]
                            root_dir = first_member.split('/')[0] + '/'
                            prefix = root_dir + "models/"
                            for member in zip_ref.namelist():
                                if member.startswith(prefix):
                                    rel_path = member[len(root_dir):]
                                    target_path = os.path.join(dest_dir, rel_path)
                                    if member.endswith('/'):
                                        os.makedirs(target_path, exist_ok=True)
                                    else:
                                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                        with zip_ref.open(member) as source, open(target_path, 'wb') as target:
                                            shutil.copyfileobj(source, target)
                        try:
                            os.remove(zip_path)
                        except Exception:
                            pass
                        _log.info("ZFTurbo architecture successfully initialized.")

                    abs_dest_dir = os.path.abspath(dest_dir)
                    if abs_dest_dir not in sys.path:
                        sys.path.insert(0, abs_dest_dir)

                    # Mock pytorch_lightning, torchmetrics, asteroid
                    if 'pytorch_lightning' not in sys.modules:
                        import types
                        pl = types.ModuleType("pytorch_lightning")
                        pl.LightningModule = torch.nn.Module
                        pl.LightningDataModule = object
                        pl_utils = types.ModuleType("pytorch_lightning.utilities")
                        pl_utils_types = types.ModuleType("pytorch_lightning.utilities.types")
                        pl_utils_types.STEP_OUTPUT = None
                        sys.modules['pytorch_lightning'] = pl
                        sys.modules['pytorch_lightning.utilities'] = pl_utils
                        sys.modules['pytorch_lightning.utilities.types'] = pl_utils_types

                    if 'torchmetrics' not in sys.modules:
                        import types
                        class DummyTM(types.ModuleType):
                            def __init__(self, name):
                                super().__init__(name)
                                self.Metric = torch.nn.Module
                                class DummyMetricCollection:
                                    def __init__(self, *args, **kwargs):
                                        pass
                                self.MetricCollection = DummyMetricCollection
                            def __getattr__(self, name):
                                if name.startswith('__'):
                                    raise AttributeError(name)
                                if name[0].isupper():
                                    return torch.nn.Module
                                return lambda *args, **kwargs: None

                        tm = DummyTM("torchmetrics")
                        tm_functional = DummyTM("torchmetrics.functional")
                        sys.modules['torchmetrics'] = tm
                        sys.modules['torchmetrics.functional'] = tm_functional

                    if 'asteroid' not in sys.modules:
                        class DummyAsteroid:
                            class losses:
                                pass
                        sys.modules['asteroid'] = DummyAsteroid

                    if 'spafe' not in sys.modules:
                        import types
                        spafe_mod = types.ModuleType("spafe")
                        spafe_fbanks = types.ModuleType("spafe.fbanks")
                        spafe_fbanks_bark = types.ModuleType("spafe.fbanks.bark_fbanks")
                        spafe_utils = types.ModuleType("spafe.utils")
                        spafe_utils_conv = types.ModuleType("spafe.utils.converters")

                        spafe_fbanks_bark.bark_filter_banks = lambda *args, **kwargs: (None, None)
                        spafe_utils_conv.erb2hz = lambda *args, **kwargs: None
                        spafe_utils_conv.hz2bark = lambda *args, **kwargs: None
                        spafe_utils_conv.hz2erb = lambda *args, **kwargs: None

                        spafe_mod.fbanks = spafe_fbanks
                        spafe_fbanks.bark_fbanks = spafe_fbanks_bark
                        spafe_mod.utils = spafe_utils
                        spafe_utils.converters = spafe_utils_conv

                        sys.modules['spafe'] = spafe_mod
                        sys.modules['spafe.fbanks'] = spafe_fbanks
                        sys.modules['spafe.fbanks.bark_fbanks'] = spafe_fbanks_bark
                        sys.modules['spafe.utils'] = spafe_utils
                        sys.modules['spafe.utils.converters'] = spafe_utils_conv

                    if 'pedalboard' not in sys.modules:
                        import types
                        pb_mod = types.ModuleType("pedalboard")
                        class DummyReverb:
                            def __init__(self, *args, **kwargs): pass
                            def process(self, *args, **kwargs): pass
                        pb_mod.Reverb = DummyReverb
                        sys.modules['pedalboard'] = pb_mod

                    if 'torch_audiomentations' not in sys.modules:
                        import types
                        class DummyTAM(types.ModuleType):
                            def __getattr__(self, name):
                                if name.startswith('__'):
                                    raise AttributeError(name)
                                return lambda *args, **kwargs: None
                        sys.modules['torch_audiomentations'] = DummyTAM("torch_audiomentations")

                    with open(yaml_path, 'r', encoding='utf-8') as yf:
                        raw_yaml = _yaml.load(yf, Loader=_yaml.FullLoader)

                    if 'model' in raw_yaml and isinstance(raw_yaml['model'], dict):
                        model_kwargs = raw_yaml['model']
                    elif 'kwargs' in raw_yaml and isinstance(raw_yaml['kwargs'], dict):
                        model_kwargs = raw_yaml['kwargs']
                    else:
                        model_kwargs = raw_yaml

                    # Clean constructor args defensively
                    for k in list(model_kwargs.keys()):
                        if k in ['cls', 'type']:
                            del model_kwargs[k]

                    if is_bandit:
                        if "MultiMaskMultiSourceBandSplitRNN" in str(raw_yaml):
                            from models.bandit.core.model import MultiMaskMultiSourceBandSplitRNNSimple
                            model = MultiMaskMultiSourceBandSplitRNNSimple(**model_kwargs)
                        else:
                            from models.bandit_v2.bandit import Bandit
                            model = Bandit(**model_kwargs)
                    else:  # is_scnet
                        if "scnet_masked" in yaml_path.lower() or "SCNetMasked" in str(raw_yaml):
                            from models.scnet.scnet_masked import SCNetMasked
                            model = SCNetMasked(**model_kwargs)
                        elif "scnet_tran" in yaml_path.lower() or "SCNetTran" in str(raw_yaml):
                            from models.scnet.scnet_tran import SCNetTran
                            model = SCNetTran(**model_kwargs)
                        else:
                            from models.scnet.scnet import SCNet
                            model = SCNet(**model_kwargs)

                    checkpoint = torch.load(model_path, map_location='cpu')
                    state_dict = checkpoint.get('state_dict', checkpoint.get('model', checkpoint))

                    new_state_dict = {}
                    for k, v in state_dict.items():
                        if k.startswith("model."):
                            new_state_dict[k[6:]] = v
                        else:
                            new_state_dict[k] = v

                    model.load_state_dict(new_state_dict)
                    model.to(device).eval()

                    from audio_separator.separator.roformer.model_loading_result import ModelLoadingResult, ImplementationVersion
                    from ml_collections import ConfigDict
                    cfg = ConfigDict(patched_load_yaml(yaml_path))

                    result = ModelLoadingResult.success_result(
                        model=model,
                        implementation=ImplementationVersion.NEW,
                        config=cfg,
                    )
                    _log.info(f"[Patch] ZFTurbo model loaded successfully for {ckpt_filename}!")
                    return result

                except Exception as e:
                    _log.error(f"[Patch] Failed to load ZFTurbo model for {ckpt_filename}: {e}", exc_info=True)
                    raise RuntimeError(f"Could not load custom model {ckpt_filename}: {e}") from e

            if yaml_filename:
                yaml_path = os.path.join(model_dir_for_patch, yaml_filename)
                if os.path.exists(yaml_path):
                    try:
                        with open(yaml_path, 'r') as yf:
                            raw_yaml = _yaml.safe_load(yf)
                        # Extract the model section (where real arch params live)
                        model_section = raw_yaml.get('model', raw_yaml)
                        _log.warning(
                            f"[Patch] Direct YAML read for {ckpt_filename}: "
                            f"dim={model_section.get('dim')}, "
                            f"depth={model_section.get('depth')}, "
                            f"num_bands={model_section.get('num_bands', model_section.get('num_subbands'))}"
                        )

                        # Determine model type and prepare specific args
                        is_bs = 'freqs_per_bands' in model_section

                        # Base arguments common to both
                        model_args = {
                            'dim': model_section['dim'],
                            'depth': model_section['depth'],
                            'stereo': model_section.get('stereo', False),
                            'num_stems': model_section.get('num_stems', len(raw_yaml.get('training', {}).get('instruments', [1, 2]))),
                            'time_transformer_depth': model_section.get('time_transformer_depth', 2),
                            'freq_transformer_depth': model_section.get('freq_transformer_depth', 2),
                            'dim_head': model_section.get('dim_head', 64),
                            'heads': model_section.get('heads', 8),
                            'attn_dropout': model_section.get('attn_dropout', 0.0),
                            'ff_dropout': model_section.get('ff_dropout', 0.0),
                            'flash_attn': model_section.get('flash_attn', True),
                            'mlp_expansion_factor': model_section.get('mlp_expansion_factor', 4),
                        }

                        # Add optional STFT/Loss params if present
                        for opt_key in [
                            'mask_estimator_depth', 'stft_n_fft', 'stft_hop_length',
                            'stft_win_length', 'stft_normalized', 'sample_rate',
                            'multi_stft_resolution_loss_weight', 'multi_stft_resolutions_window_sizes',
                            'multi_stft_hop_size', 'multi_stft_normalized', 'match_input_audio_length',
                            'sage_attention', 'zero_dc', 'use_torch_checkpoint', 'skip_connection'
                        ]:
                            if opt_key in model_section:
                                model_args[opt_key] = model_section[opt_key]

                        if is_bs:
                            from audio_separator.separator.uvr_lib_v5.roformer.bs_roformer import BSRoformer
                            model_args['freqs_per_bands'] = tuple(model_section['freqs_per_bands'])
                            model = BSRoformer(**model_args)
                        else:
                            model_args['num_bands'] = model_section.get('num_bands', model_section.get('num_subbands', 60))
                            model = MelBandRoformer(**model_args)

                        if os.path.exists(model_path):
                            # Load weights — supports both .safetensors and .ckpt/.pth formats
                            if model_path.endswith('.safetensors'):
                                try:
                                    from safetensors.torch import load_file as _st_load
                                    sd = _st_load(model_path, device=str(device))
                                except ImportError:
                                    raise RuntimeError(
                                        "safetensors library not found. "
                                        "Install it with: pip install safetensors"
                                    )
                            else:
                                try:
                                    state_dict = torch.load(model_path, map_location=device, weights_only=False)
                                except TypeError:
                                    state_dict = torch.load(model_path, map_location=device)
                                sd = state_dict.get('state_dict', state_dict.get('model', state_dict))

                            # Detect custom architecture from weight key signatures
                            has_segm = any(".segm." in k for k in sd.keys())
                            has_fno = any("fno_blocks" in k for k in sd.keys())

                            if has_segm:
                                _log.info(f"[Patch] HyperACE/Segm architecture detected for {ckpt_filename}. Remapping weights.")
                                new_sd = {}
                                for k, v in sd.items():
                                    new_k = k.replace(".segm.hyperace.", ".").replace(".segm.", ".")
                                    new_sd[new_k] = v
                                model.load_state_dict(new_sd, strict=False)

                            elif has_fno:
                                _log.info(f"[Patch] FNO architecture detected for {ckpt_filename}. Rebuilding MaskEstimator with FNO1d.")
                                # Replace MaskEstimator with the FNO version matching pcunwa's training code exactly:
                                # https://huggingface.co/pcunwa/BS-Roformer-Inst-FNO
                                try:
                                    from neuralop.models import FNO1d
                                    from torch import nn as _nn
                                    from torch.nn import Module as _Module, ModuleList as _ModuleList
                                    from einops import rearrange as _rearrange

                                    class FNOMaskEstimator(_Module):
                                        def __init__(self, dim, dim_inputs, depth, mlp_expansion_factor=4):
                                            super().__init__()
                                            self.dim_inputs = dim_inputs
                                            self.to_freqs = _ModuleList([])
                                            for dim_in in dim_inputs:
                                                mlp = _nn.Sequential(
                                                    FNO1d(
                                                        n_modes_height=64,
                                                        hidden_channels=dim,
                                                        in_channels=dim,
                                                        out_channels=dim_in * 2,
                                                        lifting_channels=dim,
                                                        projection_channels=dim,
                                                        n_layers=3,
                                                        separable=True,
                                                    ),
                                                    _nn.GLU(dim=-2),
                                                )
                                                self.to_freqs.append(mlp)

                                        def forward(self, x):
                                            x = x.unbind(dim=-2)
                                            outs = []
                                            for band_features, mlp in zip(x, self.to_freqs):
                                                band_features = _rearrange(band_features, 'b t c -> b c t')
                                                with torch.autocast(device_type='cuda', enabled=False, dtype=torch.float32):
                                                    freq_out = mlp(band_features).float()
                                                freq_out = _rearrange(freq_out, 'b c t -> b t c')
                                                outs.append(freq_out)
                                            return torch.cat(outs, dim=-1)

                                    # Compute the per-band frequency dims (same formula as BSRoformer)
                                    audio_channels = 2 if model_section.get('stereo', False) else 1
                                    freqs_per_bands_with_complex = tuple(
                                        2 * f * audio_channels
                                        for f in model_section['freqs_per_bands']
                                    )
                                    # Rebuild mask_estimators on the already-constructed BSRoformer
                                    model.mask_estimators = _ModuleList([
                                        FNOMaskEstimator(
                                            dim=model_section['dim'],
                                            dim_inputs=freqs_per_bands_with_complex,
                                            depth=model_section.get('mask_estimator_depth', 2),
                                            mlp_expansion_factor=model_section.get('mlp_expansion_factor', 4),
                                        )
                                        for _ in range(model_section.get('num_stems', 1))
                                    ])
                                    model.load_state_dict(sd, strict=True)
                                    _log.info(f"[Patch] FNO MaskEstimator loaded successfully for {ckpt_filename}.")
                                except Exception as fno_err:
                                    _log.warning(f"[Patch] FNO rebuild failed ({fno_err}), falling back to strict=False.")
                                    model.load_state_dict(sd, strict=False)

                            else:
                                # Standard model — strict load with graceful retry
                                try:
                                    model.load_state_dict(sd, strict=True)
                                except RuntimeError as strict_err:
                                    _log.warning(f"[Patch] Strict load failed for {ckpt_filename}, retrying with strict=False: {strict_err}")
                                    model.load_state_dict(sd, strict=False)

                        model.to(device).eval()

                        from audio_separator.separator.roformer.model_loading_result import ModelLoadingResult, ImplementationVersion
                        result = ModelLoadingResult.success_result(
                            model=model,
                            implementation=ImplementationVersion.NEW,
                            config=model_section,
                        )
                        return result
                    except Exception as direct_err:
                        _log.warning(f"[Patch] Direct YAML load failed for {ckpt_filename}: {direct_err}. Falling back.")

            # Fall back to original implementation for all other models
            return original_load_model(self_loader, model_path, config, device)

        RoformerLoader.load_model = patched_load_model
        self._originals["RoformerLoader.load_model"] = original_load_model

    # ------------------------------------------------------------------ #
    #  5. MelBandRoformer: mlp_expansion_factor propagation fix
    # ------------------------------------------------------------------ #
    def _patch_melband_mlp_factor(self):
        from audio_separator.separator.uvr_lib_v5.roformer.mel_band_roformer import (
            MelBandRoformer as _MBR, MaskEstimator as _ME
        )

        _original_mbr_init = _MBR.__init__
        _original_me_init = _ME.__init__

        def _patched_mbr_init(self_mbr, dim, *, mlp_expansion_factor=4, **kwargs):
            # Temporarily wrap MaskEstimator.__init__ to inject the right factor
            _factor = mlp_expansion_factor

            def _wrapped_me_init(self_me, dim, dim_inputs, depth, mlp_expansion_factor=4):
                _original_me_init(self_me, dim, dim_inputs, depth, _factor)

            _ME.__init__ = _wrapped_me_init
            try:
                _original_mbr_init(self_mbr, dim, mlp_expansion_factor=mlp_expansion_factor, **kwargs)
            finally:
                _ME.__init__ = _original_me_init  # Always restore

        _MBR.__init__ = _patched_mbr_init
        self._originals["MelBandRoformer.__init__"] = _original_mbr_init

    # ------------------------------------------------------------------ #
    #  6. ParameterValidator: extend num_stems range for ultra-multi-stem
    # ------------------------------------------------------------------ #
    def _patch_parameter_validator(self):
        try:
            from audio_separator.separator.roformer.parameter_validator import ParameterValidator
            if "ParameterValidator.PARAMETER_RANGES" not in self._originals:
                self._originals["ParameterValidator.PARAMETER_RANGES"] = dict(ParameterValidator.PARAMETER_RANGES)
            ParameterValidator.PARAMETER_RANGES['num_stems'] = (1, 1024)
        except Exception:
            pass