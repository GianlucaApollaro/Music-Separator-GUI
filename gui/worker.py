import wx
import threading
import logging
import os
import subprocess
from audio_separator.separator import Separator
from gui.i18n_manager import i18n

import re
import sys
import tempfile
import shutil
import uuid

class TqdmCaptureStream:
    def __init__(self, notify_func, original_stream):
        self.notify_func = notify_func
        self.original_stream = original_stream
        self.prog_regex = re.compile(r"(\d+)%\|")
        self.last_val = -1
        
    def write(self, buf):
        if self.original_stream:
            try:
                self.original_stream.write(buf)
            except Exception:
                pass
            
        if "%|" in buf:
            match = self.prog_regex.search(buf)
            if match:
                val = int(match.group(1))
                if val != self.last_val:
                    self.last_val = val
                    if self.notify_func:
                        wx.CallAfter(self.notify_func, val)
                
    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass

from gui.events import EVT_LOG_ID, EVT_DONE_ID, EVT_PROGRESS_ID, ProgressEvent, LogEvent, DoneEvent

class GuiLogHandler(logging.Handler):
    def __init__(self, check_stop_func=None, notify_func=None):
        super().__init__()
        self.check_stop_func = check_stop_func
        self.notify_func = notify_func

    def emit(self, record):
        msg = self.format(record)
        if self.notify_func:
            wx.CallAfter(self.notify_func, msg)
        
        # Check if we should abort (hacky way to interrupt logging if needed, 
        # normally separation is blocking, so we can't easily stop it mid-process 
        # without killing the process or if the library supports cancellation)
        if self.check_stop_func and self.check_stop_func():
            raise KeyboardInterrupt("Stopped by user")

class SeparationThread(threading.Thread):
    def __init__(self, parent, input_files, output_dir, model_name, use_gpu=True, output_format="WAV", model_name_2=None, model_name_3=None, preset_config=None, ensemble_algorithm="avg_wave", chunk_duration=None, remove_leading_numbers=False, use_subfolder=True, delete_silent_stems=False):
        super().__init__()
        self.parent = parent
        self.input_files = input_files
        self.output_dir = output_dir
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.output_format = output_format
        self.model_name_2 = model_name_2
        self.model_name_3 = model_name_3
        self.preset_config = preset_config
        self.ensemble_algorithm = ensemble_algorithm
        self.chunk_duration = chunk_duration
        self.remove_leading_numbers = remove_leading_numbers
        self.use_subfolder = use_subfolder
        self.delete_silent_stems = delete_silent_stems
        self._stop_event = threading.Event()
        self.all_output_files = []  # accumulates absolute paths of all generated stems

    def run(self):
        try:
            # GPU/CPU enforcement logic
            old_cuda_env = os.environ.get('CUDA_VISIBLE_DEVICES')
            if not self.use_gpu:
                os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
                import torch
                self._old_is_available = torch.cuda.is_available
                torch.cuda.is_available = lambda: False
                # Also disable MPS on Apple Silicon
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    self._old_mps_is_available = torch.backends.mps.is_available
                    torch.backends.mps.is_available = lambda: False
                try:
                    import onnxruntime
                    self._old_get_providers = onnxruntime.get_available_providers
                    onnxruntime.get_available_providers = lambda: ['CPUExecutionProvider']
                except ImportError:
                    pass
            
            logger = logging.getLogger("audio_separator")
            logger.setLevel(logging.INFO)
            for h in logger.handlers:
                logger.removeHandler(h)
            
            handler = GuiLogHandler(notify_func=self.post_log)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            self.post_log(i18n.tr("status_initializing", model=self.model_name))

            if self.chunk_duration:
                self.post_log(f"Chunking enabled: {self.chunk_duration}s per segment.")

            from gui.utils import get_app_data_dir
            model_dir = os.path.join(get_app_data_dir(), 'models')
            separator = Separator(
                log_level=logging.INFO,
                model_file_dir=model_dir,
                output_dir=self.output_dir,
                chunk_duration=self.chunk_duration
            )

            # --- RUNTIME LIBRARY PATCH (MONKEY-PATCH) ---
            # We augment the library's internal model registry in memory to support custom models.
            try:
                original_list_func = separator.list_supported_model_files
                def patched_list_supported_model_files():
                    models = original_list_func()
                    
                    # Custom Roformers (MDXC) to inject
                    custom_mdxc = {
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
                        }
                    }
                    
                    if "MDXC" not in models:
                        models["MDXC"] = {}
                    models["MDXC"].update(custom_mdxc)
                    
                    # Inject all models from parent's downloadable_models so they are natively supported
                    if getattr(self, "parent", None) and hasattr(self.parent, "downloadable_models"):
                        for friendly_name, file_info in self.parent.downloadable_models.items():
                            model_type = "MDXC" # Default
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
                            
                            if model_type == "MDXC" and ("roformer" in friendly_name.lower() or "roformer" in target_file.lower()):
                                models[model_type][friendly_name]["is_roformer"] = True
                            
                    # Inject models from downloadable_models_by_file (ensures newly added pcunwa models are found)
                    if getattr(self, "parent", None) and hasattr(self.parent, "model_manager"):
                        mm = self.parent.model_manager
                        for filename, file_info in mm.downloadable_models_by_file.items():
                            model_type = "MDXC"
                            if filename.endswith('.onnx'): model_type = "MDX"
                            elif filename.endswith('.pth'): model_type = "VR"
                            elif filename.endswith('.th') or 'demucs' in filename.lower(): model_type = "Demucs"

                            if model_type not in models: models[model_type] = {}
                            
                            # Avoid duplicates
                            if any(m.get("filename") == filename for m in models[model_type].values()):
                                continue
                                
                            models[model_type][filename] = {
                                "filename": filename,
                                "download_files": list(file_info.keys())
                            }
                            if model_type == "MDXC" and "roformer" in filename.lower():
                                models[model_type][filename]["is_roformer"] = True
                    return models
                
                # Apply patch to the instance
                separator.list_supported_model_files = patched_list_supported_model_files

                # --- ROFORMER CONFIG DIRECT-READ PATCH ---
                # audio-separator has a bug: when loading a YAML that has 'model: { dim: 256, ... }'
                # the ConfigurationNormalizer fails to flatten it properly and uses wrong defaults.
                # We patch RoformerLoader.load_model to detect this case and read params from the
                # YAML directly, keyed by model_path, before calling the broken normalizer.
                import yaml as _yaml

                # Register a constructor for !!python/tuple (used in some model YAML files)
                def _tuple_constructor(loader, node):
                    return tuple(loader.construct_sequence(node))
                _yaml.SafeLoader.add_constructor(
                    'tag:yaml.org,2002:python/tuple', _tuple_constructor
                )

                from audio_separator.separator.roformer.roformer_loader import RoformerLoader
                from audio_separator.separator.uvr_lib_v5.roformer.mel_band_roformer import MelBandRoformer

                original_load_model = RoformerLoader.load_model
                model_dir_for_patch = model_dir

                # Map from model filename to its corresponding .yaml filename
                custom_ckpt_to_yaml = {
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
                }

                # --- PYTORCH 2.6+ WEIGHTS_ONLY FIX (Hardened) ---
                import torch
                import torch.serialization
                
                # Allowlist common Roformer globals globally
                try:
                    # GELU is often the culprit in UVR models
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
                            # safetensors files start with a uint64 little-endian length.
                            # Pickle files start with 0x80 (128). safetensors first bytes
                            # are never 0x80, and torch.load fails with 'invalid load key'.
                            # Safest check: the file extension or the path ends with .safetensors
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

                def patched_load_model(self_loader, model_path, config, device='cpu'):
                    import torch, logging as _logging
                    _log = _logging.getLogger(__name__)

                    ckpt_filename = os.path.basename(model_path)
                    yaml_filename = custom_ckpt_to_yaml.get(ckpt_filename)

                    if not yaml_filename:
                        # Try to find it in ModelManager's registries (closure access to self.parent)
                        if getattr(self, "parent", None) and hasattr(self.parent, "model_manager"):
                            mm = self.parent.model_manager
                            info = mm.downloadable_models_by_file.get(ckpt_filename)
                            if info:
                                for f in info.keys():
                                    if f.endswith('.yaml'):
                                        yaml_filename = f
                                        break
                    
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
                                    'num_stems': model_section.get('num_stems', 2),
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
                                    has_fno  = any("fno_blocks" in k for k in sd.keys())
                                    
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
                                            model.mask_estimators = _nn.ModuleList([
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

                # --- MASK ESTIMATOR mlp_expansion_factor PROPAGATION FIX ---
                # Bug in the library: MelBandRoformer stores mlp_expansion_factor but
                # never passes it to MaskEstimator, which always uses its default of 4.
                # Models like Becruily Guitar use mlp_expansion_factor=1, causing a size
                # mismatch ([1040, 1024] vs expected [1040, 256]).
                # Fix: patch MelBandRoformer.__init__ to temporarily override
                # MaskEstimator so it captures the correct factor from the outer scope.
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

            except Exception as patch_err:
                self.post_log(f"Warning: Runtime patch failed: {patch_err}. Custom models might fail.")
            # --- END OF PATCHES ---

            total_files = len(self.input_files)
            for file_idx, current_input_file in enumerate(self.input_files, 1):
                if self._stop_event.is_set():
                    break
                self.post_log(f"\n--- Processing file {file_idx}/{total_files} ---")
                self.post_log(f"File: {current_input_file}")
                
                # --- Create a safe ASCII file path for processing to bypass FFmpeg/AudioSeparator unicode issues ---
                # We also convert to WAV, downmix to stereo (-ac 2), and strip video streams (-vn).
                safe_base = f"audio_in_{uuid.uuid4().hex[:8]}"
                safe_input_file = os.path.join(tempfile.gettempdir(), f"{safe_base}.wav")
                
                try:
                    # -ac 2: downmix any multi-channel audio (e.g. 5.1) to stereo; no effect if already stereo/mono
                    subprocess.run(
                        ['ffmpeg', '-y', '-i', current_input_file, '-vn', '-ac', '2', safe_input_file],
                        check=True, capture_output=True
                    )
                except Exception as e:
                    self.post_log(f"FFmpeg conversion notice: {e}. Falling back to direct copy.")
                    _, input_ext = os.path.splitext(current_input_file)
                    safe_input_file = os.path.join(tempfile.gettempdir(), f"{safe_base}{input_ext}")
                    shutil.copy2(current_input_file, safe_input_file)

                # --- Peak normalization to -0.1 dBFS ---
                # Step 1: detect current peak with volumedetect
                try:
                    self.post_log(i18n.tr("status_normalizing"))
                    vol_result = subprocess.run(
                        ['ffmpeg', '-y', '-i', safe_input_file, '-af', 'volumedetect', '-f', 'null',
                         os.devnull if os.name != 'nt' else 'NUL'],
                        capture_output=True, text=True
                    )
                    peak_match = re.search(r'max_volume:\s*([-\d.]+)\s*dB', vol_result.stderr)
                    if peak_match:
                        max_vol_db = float(peak_match.group(1))
                        gain_db = -0.1 - max_vol_db  # gain needed to bring peak to -0.1 dBFS
                        if abs(gain_db) > 0.01:  # skip if already within 0.01 dB of target
                            norm_file = os.path.join(tempfile.gettempdir(), f"{safe_base}_norm.wav")
                            subprocess.run(
                                ['ffmpeg', '-y', '-i', safe_input_file, '-af', f'volume={gain_db:.4f}dB', norm_file],
                                check=True, capture_output=True
                            )
                            os.replace(norm_file, safe_input_file)
                except Exception as norm_err:
                    self.post_log(f"Normalization skipped: {norm_err}")

                base_input_name = os.path.splitext(os.path.basename(current_input_file))[0]

                # Optional: Remove leading numbers from the folder name
                folder_name = base_input_name
                if self.remove_leading_numbers:
                    folder_name = re.sub(r"^\d+[\s.\-_]+", "", base_input_name)

                # Output directory: dedicated subfolder (default) or flat into output_dir
                if self.use_subfolder:
                    file_output_dir = os.path.join(self.output_dir, folder_name)
                    os.makedirs(file_output_dir, exist_ok=True)
                else:
                    file_output_dir = self.output_dir
                separator.output_dir = file_output_dir

                if self.preset_config:
                    preset_type = self.preset_config.get("type", "chain")

                    if preset_type == "single":
                        # ====== PRESET SINGLE MODEL (Filter/Rename Stems) ======
                        from gui.audio_utils import stem_from_filename
                        self.post_log(i18n.tr("status_loading"))
                        separator.load_model(model_filename=self.preset_config["model_1"])
                        self.post_log(i18n.tr("status_starting", file=os.path.basename(current_input_file)))
                        
                        old_stderr = sys.stderr
                        sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                        try:
                            m1_outputs = separator.separate(safe_input_file)
                        finally:
                            sys.stderr = old_stderr
                        
                        final_outputs = []
                        rename_map = self.preset_config.get("rename_map", {})
                        
                        for f in m1_outputs:
                            stem = stem_from_filename(f)
                            clean_ext = os.path.splitext(f)[1]
                            old_path = os.path.join(file_output_dir, f)
                            
                            if stem in rename_map:
                                suffix = rename_map[stem].lstrip('_')
                                # Prepend original filename if not using subfolders
                                if not self.use_subfolder:
                                    new_name = f"{folder_name}_{suffix}{clean_ext}"
                                else:
                                    new_name = f"{suffix}{clean_ext}"
                                
                                new_path = os.path.join(file_output_dir, new_name)
                                if os.path.exists(new_path):
                                    os.remove(new_path)
                                os.rename(old_path, new_path)
                                final_outputs.append(new_name)
                            else:
                                # Delete unwanted stems
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                        
                        output_files = final_outputs

                    elif preset_type == "ensemble":

                        # ====== PRESET ENSEMBLE (2-Pass + Local Mixing) ======
                        import soundfile as sf
                        import numpy as np
                        from gui.audio_utils import blend_audio, stem_from_filename

                        algorithm = self.preset_config.get("algorithm", "avg_wave")
                        temp_dir_1 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_1_")
                        temp_dir_2 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_2_")

                        # Pass 1
                        self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 1: {self.preset_config['model_1']})")
                        separator.output_dir = temp_dir_1
                        separator.load_model(model_filename=self.preset_config["model_1"])
                        old_stderr = sys.stderr
                        sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                        try:
                            output_files_1 = separator.separate(safe_input_file)
                        finally:
                            sys.stderr = old_stderr

                        # Pass 2
                        self.post_progress(0)
                        self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 2: {self.preset_config['model_2']})")
                        separator.output_dir = temp_dir_2
                        separator.load_model(model_filename=self.preset_config["model_2"])
                        old_stderr = sys.stderr
                        sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                        try:
                            output_files_2 = separator.separate(safe_input_file)
                        finally:
                            sys.stderr = old_stderr

                        # Blending
                        self.post_log(i18n.tr("status_ensemble_mixing") + f" [{algorithm}]")
                        final_outputs = []
                        for f1 in output_files_1:
                            stem1 = stem_from_filename(f1)
                            match_2 = [f for f in output_files_2 if stem_from_filename(f) == stem1]
                            clean_ext = os.path.splitext(f1)[1]
                            if match_2:
                                d1, sr1 = sf.read(os.path.join(temp_dir_1, f1))
                                d2, _ = sf.read(os.path.join(temp_dir_2, match_2[0]))
                                min_len = min(len(d1), len(d2))
                                mixed = blend_audio(d1[:min_len], d2[:min_len], algorithm)
                                out_name = f"(Ensemble_{stem1.capitalize()}){clean_ext}"
                                sf.write(os.path.join(file_output_dir, out_name), mixed, sr1)
                                final_outputs.append(out_name)
                            else:
                                out_name = f"(Ensemble_{stem1.capitalize()}_M1){clean_ext}"
                                shutil.copy(os.path.join(temp_dir_1, f1), os.path.join(file_output_dir, out_name))
                                final_outputs.append(out_name)

                        shutil.rmtree(temp_dir_1, ignore_errors=True)
                        shutil.rmtree(temp_dir_2, ignore_errors=True)
                        output_files = final_outputs
                        self.post_log(i18n.tr("status_ensemble_done"))

                    else:
                        # ====== CHAINED PRESET MULTI-PASS ======


                        temp_dir_1 = tempfile.mkdtemp(dir=self.output_dir, prefix="chain_1_")
                        temp_dir_2 = tempfile.mkdtemp(dir=self.output_dir, prefix="chain_2_")
                        final_outputs = []
                        from gui.audio_utils import stem_from_filename
                    
                        # Model 1
                        self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 1: {self.preset_config['model_1']})")
                        separator.output_dir = temp_dir_1
                        separator.load_model(model_filename=self.preset_config['model_1'])
                    
                        old_stderr = sys.stderr
                        sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                        try:
                            output_files_1 = separator.separate(safe_input_file)
                        finally:
                            sys.stderr = old_stderr

                        pass_file_path = None
                        pass_stem = self.preset_config["pass_stem"].lower()
                    
                        for f1 in output_files_1:
                            stem1 = stem_from_filename(f1)
                            clean_ext = os.path.splitext(f1)[1]
                        
                            # Tratta 'other' e 'instrumental' come sinonimi per la decisione di quale stelo passare al M2
                            stem_match = (stem1 == pass_stem) or (stem1 in ["other", "instrumental"] and pass_stem in ["other", "instrumental"])
                        
                            if stem_match:
                                pass_file_path = os.path.join(temp_dir_1, f1)
                                if "m1_keep_pass_stem_name" in self.preset_config:
                                    suffix = self.preset_config["m1_keep_pass_stem_name"].lstrip('_')
                                    if not self.use_subfolder:
                                        out_name = f"{folder_name}_{suffix}{clean_ext}"
                                    else:
                                        out_name = f"{suffix}{clean_ext}"
                                    final_path = os.path.join(file_output_dir, out_name)
                                    shutil.copy(os.path.join(temp_dir_1, f1), final_path)
                                    final_outputs.append(out_name)
                            else:
                                suffix = self.preset_config.get("m1_keep_name", "_Instrumental").lstrip('_')
                                if not self.use_subfolder:
                                    out_name = f"{folder_name}_{suffix}{clean_ext}"
                                else:
                                    out_name = f"{suffix}{clean_ext}"
                                final_path = os.path.join(file_output_dir, out_name)
                                shutil.copy(os.path.join(temp_dir_1, f1), final_path)
                                final_outputs.append(out_name)
                            
                        if pass_file_path:
                            # Model 2
                            self.post_progress(0)
                            self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 2: {self.preset_config['model_2']})")
                            separator.output_dir = temp_dir_2
                            separator.load_model(model_filename=self.preset_config['model_2'])
                        
                            old_stderr = sys.stderr
                            sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                            try:
                                output_files_2 = separator.separate(pass_file_path)
                            finally:
                                sys.stderr = old_stderr

                            pass_file_path_2 = None
                            pass_stem_2 = self.preset_config.get("pass_stem_2", "").lower()
                            rename_map = self.preset_config.get("m2_rename_map", {})
                        
                            for f2 in output_files_2:
                                stem2 = stem_from_filename(f2)
                                clean_ext = os.path.splitext(f2)[1]
                            
                                # Check if this stem should be passed to model 3
                                stem_match_2 = (pass_stem_2 != "" and (stem2 == pass_stem_2 or (stem2 in ["other", "instrumental"] and pass_stem_2 in ["other", "instrumental"])))
                                
                                if stem2 in rename_map:
                                    suffix = rename_map[stem2]
                                    if suffix is None: # Discard
                                        continue
                                else:
                                    suffix = f"_{stem2.capitalize()}"
                                
                                suffix = suffix.lstrip('_')
                                if not self.use_subfolder:
                                    out_name = f"{folder_name}_{suffix}{clean_ext}"
                                else:
                                    out_name = f"{suffix}{clean_ext}"
                                final_path = os.path.join(file_output_dir, out_name)
                                
                                if stem_match_2:
                                    pass_file_path_2 = os.path.join(temp_dir_2, f2)
                                    # Users might want to keep the passed stem too (e.g. stereo drums)
                                    if "m2_keep_pass_stem_name" in self.preset_config or stem2 in rename_map:
                                        # If it's in the rename map, it means we want to keep it
                                        shutil.copy(os.path.join(temp_dir_2, f2), final_path)
                                        final_outputs.append(out_name)
                                else:
                                    shutil.copy(os.path.join(temp_dir_2, f2), final_path)
                                    final_outputs.append(out_name)

                            if pass_file_path_2 and self.model_name_3:
                                # Model 3
                                temp_dir_3 = tempfile.mkdtemp(dir=self.output_dir, prefix="chain_3_")
                                self.post_progress(0)
                                self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 3: {self.model_name_3})")
                                separator.output_dir = temp_dir_3
                                separator.load_model(model_filename=self.model_name_3)
                            
                                old_stderr = sys.stderr
                                sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                                try:
                                    output_files_3 = separator.separate(pass_file_path_2)
                                finally:
                                    sys.stderr = old_stderr
                                
                                for f3 in output_files_3:
                                    stem3 = stem_from_filename(f3)
                                    clean_ext = os.path.splitext(f3)[1]
                                    
                                    rename_map_3 = self.preset_config.get("m3_rename_map", {})
                                    if stem3 in rename_map_3:
                                        suffix = rename_map_3[stem3]
                                        if suffix is None: continue
                                    else:
                                        suffix = f"_{stem3.capitalize()}"
                                    
                                    suffix = suffix.lstrip('_')
                                    if not self.use_subfolder:
                                        out_name = f"{folder_name}_{suffix}{clean_ext}"
                                    else:
                                        out_name = f"{suffix}{clean_ext}"
                                    
                                    final_path = os.path.join(file_output_dir, out_name)
                                    shutil.copy(os.path.join(temp_dir_3, f3), final_path)
                                    final_outputs.append(out_name)
                                
                                shutil.rmtree(temp_dir_3, ignore_errors=True)
                        else:
                            self.post_log(f"Warning: Could not find '{pass_stem}' stem from Pass 1 to feed into Pass 2.")
                    
                        shutil.rmtree(temp_dir_1, ignore_errors=True)
                        shutil.rmtree(temp_dir_2, ignore_errors=True)
                    
                        output_files = final_outputs
                        self.post_log(i18n.tr("status_ensemble_done"))

                elif not self.model_name_2:
                    # ====== STANDARD SINGLE MODEL PASS ======
                    self.post_log(i18n.tr("status_loading"))
                    separator.load_model(model_filename=self.model_name)
                    self.post_log(i18n.tr("status_starting", file=os.path.basename(current_input_file)))
                
                    old_stderr = sys.stderr
                    sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                    try:
                        output_files = separator.separate(safe_input_file)
                    finally:
                        sys.stderr = old_stderr

                    renamed_output_files = []
                    for f in output_files:
                        old_path = os.path.join(file_output_dir, f)
                        if os.path.exists(old_path):
                            # Strip the temp safe_base prefix, keep only stem+model part
                            suffix = f.replace(safe_base, "").lstrip("_")
                            if not self.use_subfolder:
                                new_name = f"{folder_name}_{suffix}"
                            else:
                                new_name = suffix
                            
                            new_path = os.path.join(file_output_dir, new_name)
                            if os.path.exists(new_path) and old_path != new_path:
                                os.remove(new_path)
                            os.rename(old_path, new_path)
                            renamed_output_files.append(new_name)
                        else:
                            renamed_output_files.append(f)
                    output_files = renamed_output_files
                else:
                    # ====== ENSEMBLE DUAL MODEL PASS (2-Pass + Local Mixing) ======
                    import soundfile as sf
                    import numpy as np

                    algorithm = self.ensemble_algorithm
                    temp_dir_1 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_1_")
                    temp_dir_2 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_2_")
                    base_input_name = os.path.splitext(os.path.basename(current_input_file))[0]

                    from gui.audio_utils import stem_from_filename, blend_audio

                    # Pass 1
                    self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 1: {self.model_name})")
                    separator.output_dir = temp_dir_1
                    separator.load_model(model_filename=self.model_name)
                    old_stderr = sys.stderr
                    sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                    try:
                        output_files_1 = separator.separate(safe_input_file)
                    finally:
                        sys.stderr = old_stderr

                    # Pass 2
                    self.post_progress(0)
                    self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 2: {self.model_name_2})")
                    separator.output_dir = temp_dir_2
                    separator.load_model(model_filename=self.model_name_2)
                    old_stderr = sys.stderr
                    sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                    try:
                        output_files_2 = separator.separate(safe_input_file)
                    finally:
                        sys.stderr = old_stderr

                    # Blending
                    self.post_log(i18n.tr("status_ensemble_mixing") + f" [{algorithm}]")
                    final_outputs = []
                    for f1 in output_files_1:
                        stem1 = stem_from_filename(f1)
                        if stem1 == "other": stem1 = "instrumental" # Compatibility
                        
                        match_2 = [f for f in output_files_2 if stem_from_filename(f) in (stem1, "other" if stem1 == "instrumental" else None)]
                        clean_ext = os.path.splitext(f1)[1]
                        if match_2:
                            d1, sr1 = sf.read(os.path.join(temp_dir_1, f1))
                            d2, _ = sf.read(os.path.join(temp_dir_2, match_2[0]))
                            mixed = blend_audio(d1, d2, algorithm)
                            
                            suffix = stem1.capitalize()
                            if not self.use_subfolder:
                                out_name = f"{folder_name}_Ensemble_{suffix}{clean_ext}"
                            else:
                                out_name = f"Ensemble_{suffix}{clean_ext}"
                            
                            sf.write(os.path.join(file_output_dir, out_name), mixed, sr1)
                            final_outputs.append(out_name)
                        else:
                            suffix = f"{stem1.capitalize()}_M1"
                            if not self.use_subfolder:
                                out_name = f"{folder_name}_Ensemble_{suffix}{clean_ext}"
                            else:
                                out_name = f"Ensemble_{suffix}{clean_ext}"
                                
                            shutil.copy(os.path.join(temp_dir_1, f1), os.path.join(file_output_dir, out_name))
                            final_outputs.append(out_name)
                    # Stems only in M2
                    for f2 in output_files_2:
                        stem2 = stem_from_filename(f2)
                        if stem2 == "other": stem2 = "instrumental"
                        
                        if not any(stem_from_filename(f) in (stem2, "other" if stem2 == "instrumental" else None) for f in output_files_1):
                            clean_ext = os.path.splitext(f2)[1]
                            suffix = f"{stem2.capitalize()}_M2"
                            if not self.use_subfolder:
                                out_name = f"{folder_name}_Ensemble_{suffix}{clean_ext}"
                            else:
                                out_name = f"Ensemble_{suffix}{clean_ext}"
                                
                            shutil.copy(os.path.join(temp_dir_2, f2), os.path.join(file_output_dir, out_name))
                            final_outputs.append(out_name)

                    shutil.rmtree(temp_dir_1, ignore_errors=True)
                    shutil.rmtree(temp_dir_2, ignore_errors=True)
                    output_files = final_outputs
                    self.post_log(i18n.tr("status_ensemble_done"))
            
                if self.output_format != "WAV":
                    new_files = []
                    for file in output_files:
                        try:
                            old_path = os.path.join(file_output_dir, file)
                            base, _ = os.path.splitext(file)
                            new_ext = f".{self.output_format.lower()}"
                            new_filename = f"{base}{new_ext}"
                            new_path = os.path.join(file_output_dir, new_filename)
                        
                            self.post_log(i18n.tr("status_converting", file=file, format=self.output_format))
                        
                            if self.output_format == "FLAC":
                                cmd = ["ffmpeg", "-y", "-i", old_path, "-c:a", "flac", "-sample_fmt", "s16", new_path]
                            else:
                                cmd = ["ffmpeg", "-y", "-i", old_path, "-c:a", "libmp3lame", "-b:a", "320k", new_path]
                            
                            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                            if result.returncode == 0:
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                                new_files.append(new_filename)
                            else:
                                self.post_log(f"FFmpeg conversion failed for {file}")
                                new_files.append(file)
                        except Exception as ex:
                            self.post_log(f"Error converting {file}: {ex}")
                            new_files.append(file)
                    output_files = new_files
                
                if safe_input_file and os.path.exists(safe_input_file):
                    try:
                        os.remove(safe_input_file)
                    except Exception:
                        pass

                # --- Silent stem detection and optional deletion ---
                if self.delete_silent_stems and output_files:
                    surviving = []
                    for fname in output_files:
                        fpath = os.path.join(file_output_dir, fname)
                        if not os.path.exists(fpath):
                            surviving.append(fname)
                            continue
                        try:
                            vol_res = subprocess.run(
                                ['ffmpeg', '-y', '-i', fpath, '-af', 'volumedetect', '-f', 'null',
                                 os.devnull if os.name != 'nt' else 'NUL'],
                                capture_output=True, text=True
                            )
                            peak_m = re.search(r'max_volume:\s*([-\d.]+)\s*dB', vol_res.stderr)
                            if peak_m and float(peak_m.group(1)) < -50.0:
                                os.remove(fpath)
                                self.post_log(i18n.tr("status_silent_stem_deleted", file=fname))
                            else:
                                surviving.append(fname)
                                self.all_output_files.append(fpath)
                        except Exception:
                            surviving.append(fname)
                            self.all_output_files.append(fpath)
                    output_files = surviving
                else:
                    for fname in output_files:
                        fpath = os.path.join(file_output_dir, fname)
                        if os.path.exists(fpath):
                            self.all_output_files.append(fpath)

            self.post_progress(100)
            self.post_log(i18n.tr("status_complete", files=output_files))
            wx.PostEvent(self.parent, DoneEvent(True, i18n.tr("msg_success"), output_files=self.all_output_files))

        except Exception as e:
            import traceback
            error_msg = str(e)
            if not error_msg.strip():
                error_msg = getattr(e, 'message', repr(e))
            full_trace = traceback.format_exc()
            error_msg += f"\n\nTraceback:\n{full_trace}"
            print(f"Exception during separation: {full_trace}")
            # Detect Apple Silicon MPS out-of-memory error and show a clear message
            if "MPS backend out of memory" in error_msg or "MPS allocated" in error_msg:
                friendly = (
                    "⚠️ Out of Memory (Apple Silicon MPS)\n\n"
                    "The model requires more memory than available on the GPU.\n"
                    "Suggestions:\n"
                    "  • Try a smaller/lighter model\n"
                    "  • Enable the 'CPU only' option to avoid GPU memory limits\n"
                    "  • Close other apps to free RAM\n\n"
                    f"Technical detail: {error_msg}"
                )
                self.post_log(friendly)
                wx.PostEvent(self.parent, DoneEvent(False, friendly))
            else:
                self.post_log(i18n.tr("status_error", error=error_msg))
                wx.PostEvent(self.parent, DoneEvent(False, error_msg))
            
        finally:
            # Always cleanly restore the patched variables for subsequent GPU runs
            if not self.use_gpu:
                if old_cuda_env is not None:
                    os.environ['CUDA_VISIBLE_DEVICES'] = old_cuda_env
                elif 'CUDA_VISIBLE_DEVICES' in os.environ:
                    del os.environ['CUDA_VISIBLE_DEVICES']
                
                try:
                    import torch
                    if hasattr(self, '_old_is_available'):
                        torch.cuda.is_available = self._old_is_available
                    if hasattr(self, '_old_mps_is_available'):
                        torch.backends.mps.is_available = self._old_mps_is_available
                except ImportError:
                    pass
                
                try:
                    import onnxruntime
                    if hasattr(self, '_old_get_providers'):
                        onnxruntime.get_available_providers = self._old_get_providers
                except ImportError:
                    pass
            
            # Restore original torch loading functions
            try:
                import torch, torch.serialization
                if '_original_torch_load' in locals():
                    torch.load = _original_torch_load
                if '_original_serialization_load' in locals():
                    torch.serialization.load = _original_serialization_load
            except ImportError:
                pass

    def post_progress(self, value, maximum=100):
        wx.PostEvent(self.parent, ProgressEvent(value, maximum))

    def post_log(self, message):
        wx.PostEvent(self.parent, LogEvent(message))

    def stop(self):
        self._stop_event.set()
