import wx
import threading
import logging
import os
import subprocess
import re
import sys
import tempfile
import shutil
import uuid
import traceback
import soundfile as sf
import numpy as np
from audio_separator.separator import Separator
from gui.i18n_manager import i18n
from gui.audio_utils import stem_from_filename, blend_audio, get_model_stems, stems_are_equivalent, get_rename_suffix, get_audio_volume_stats

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
    def __init__(self, parent, input_files, output_dir, model_name, use_gpu=True, output_format="WAV", model_name_2=None, model_name_3=None, model_name_4=None, model_name_5=None, preset_config=None, ensemble_algorithm="avg_wave", chunk_duration=None, remove_leading_numbers=False, use_subfolder=True, delete_silent_stems=False, silent_stem_threshold=-50.0, enable_preview=False, preview_mode="first", bit_depth=None, bitrate=None, on_progress=None, on_log=None, on_done=None):
        super().__init__()
        self.parent = parent
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_done = on_done
        self.input_files = input_files
        self.output_dir = output_dir
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.output_format = output_format
        self.bit_depth = bit_depth or "24-bit"
        self.bitrate = bitrate or "320k"
        self.model_name_2 = model_name_2
        self.model_name_3 = model_name_3
        self.model_name_4 = model_name_4
        self.model_name_5 = model_name_5
        self.preset_config = preset_config
        self.ensemble_algorithm = ensemble_algorithm
        self.chunk_duration = chunk_duration
        self.remove_leading_numbers = remove_leading_numbers
        self.use_subfolder = use_subfolder
        self.delete_silent_stems = delete_silent_stems
        self.silent_stem_threshold = float(silent_stem_threshold) if silent_stem_threshold is not None else -50.0
        self.enable_preview = enable_preview
        self.preview_mode = preview_mode
        self._stop_event = threading.Event()
        self.all_output_files = []  # accumulates absolute paths of all generated stems
        self._temp_dirs = []  # temp dirs created during separation, cleaned in run()'s finally

        if self.enable_preview:
            parent_dir = os.path.dirname(self.output_dir)
            if parent_dir:
                self.output_dir = os.path.join(parent_dir, "previews")
            else:
                self.output_dir = "previews"

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
            while logger.handlers:
                logger.removeHandler(logger.handlers[0])
            
            handler = GuiLogHandler(notify_func=self.post_log)
            formatter = logging.Formatter('%(message)s [%(asctime)s - %(levelname)s]', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            self.post_log(i18n.tr("status_initializing", model=self.model_name))

            if self.enable_preview:
                os.makedirs(self.output_dir, exist_ok=True)
                if self.preview_mode == "final":
                    self.post_log(i18n.tr("log_preview_final"))
                else:
                    self.post_log(i18n.tr("log_preview_first"))

            if self.chunk_duration:
                self.post_log(i18n.tr("log_chunk_enabled", seconds=self.chunk_duration))

            from gui.utils import get_app_data_dir
            model_dir = os.path.join(get_app_data_dir(), 'models')
            separator = Separator(
                log_level=logging.INFO,
                model_file_dir=model_dir,
                output_dir=self.output_dir,
                chunk_duration=self.chunk_duration
            )

            # --- RUNTIME LIBRARY PATCH (MONKEY-PATCH) ---
            # Custom model support is implemented in gui/audio_patches.py (AudioPatches).
            from gui.audio_patches import AudioPatches

            patcher = AudioPatches(model_dir=model_dir, parent=self.parent, log=self.post_log)
            try:
                patcher.apply(separator)
            except Exception as patch_err:
                self.post_log(i18n.tr("log_patch_failed", error=patch_err))
            # --- END OF PATCHES ---

            total_files = len(self.input_files)
            for file_idx, current_input_file in enumerate(self.input_files, 1):
                if self._stop_event.is_set():
                    break
                self.post_log(i18n.tr("log_processing_file", index=file_idx, total=total_files))
                self.post_log(i18n.tr("log_file", file=current_input_file))
                
                # --- Create a safe ASCII file path for processing to bypass FFmpeg/AudioSeparator unicode issues ---
                # We also convert to WAV, downmix to stereo (-ac 2), and strip video streams (-vn).
                safe_base = f"audio_in_{uuid.uuid4().hex[:8]}"
                safe_input_file = os.path.join(tempfile.gettempdir(), f"{safe_base}.wav")
                
                try:
                    # -ac 2: downmix any multi-channel audio (e.g. 5.1) to stereo; no effect if already stereo/mono
                    if self.enable_preview and self.preview_mode == "final":
                        ffmpeg_cmd = ['ffmpeg', '-y', '-sseof', '-30', '-i', current_input_file, '-vn', '-ac', '2', safe_input_file]
                    else:
                        ffmpeg_cmd = ['ffmpeg', '-y', '-i', current_input_file, '-vn', '-ac', '2']
                        if self.enable_preview:
                            ffmpeg_cmd += ['-t', '30']
                        ffmpeg_cmd.append(safe_input_file)
                    
                    subprocess.run(
                        ffmpeg_cmd,
                        check=True, capture_output=True
                    )
                except Exception as e:
                    self.post_log(i18n.tr("log_ffmpeg_notice", error=e))

                if not os.path.exists(safe_input_file):
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
                    self.post_log(i18n.tr("log_normalization_skipped", error=norm_err))

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
                        mix_remaining_to = self.preset_config.get("mix_remaining_to")
                        
                        clean_ext = ".wav"
                        if m1_outputs:
                            clean_ext = os.path.splitext(m1_outputs[0])[1]
                            
                        paths_to_mix = []
                        
                        for f in m1_outputs:
                            stem = stem_from_filename(f)
                            old_path = os.path.join(file_output_dir, f)
                            
                            found_map, suffix_val = get_rename_suffix(stem, rename_map)
                            if found_map and suffix_val is not None:
                                suffix = suffix_val.lstrip('_')
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
                                if mix_remaining_to:
                                    paths_to_mix.append(old_path)
                                else:
                                    if os.path.exists(old_path):
                                        os.remove(old_path)
                                        
                        if mix_remaining_to and paths_to_mix:
                            self.post_log(i18n.tr("status_ensemble_mixing") or "Mixing remaining stems...")
                            mixed_data = None
                            samplerate = None
                            
                            for path in paths_to_mix:
                                if os.path.exists(path):
                                    data, sr = sf.read(path)
                                    if samplerate is None:
                                        samplerate = sr
                                    if mixed_data is None:
                                        mixed_data = data
                                    else:
                                        min_len = min(len(mixed_data), len(data))
                                        mixed_data = mixed_data[:min_len] + data[:min_len]
                                        
                            if mixed_data is not None and samplerate is not None:
                                suffix = mix_remaining_to.lstrip('_')
                                if not self.use_subfolder:
                                    mix_name = f"{folder_name}_{suffix}{clean_ext}"
                                else:
                                    mix_name = f"{suffix}{clean_ext}"
                                    
                                mix_path = os.path.join(file_output_dir, mix_name)
                                if os.path.exists(mix_path):
                                    os.remove(mix_path)
                                sf.write(mix_path, mixed_data, samplerate)
                                final_outputs.append(mix_name)
                                
                            for path in paths_to_mix:
                                if os.path.exists(path):
                                    try:
                                        os.remove(path)
                                    except Exception:
                                        pass
                                        
                        output_files = final_outputs

                    elif preset_type == "ensemble":

                        # ====== PRESET ENSEMBLE (2-Pass + Local Mixing) ======
                        algorithm = self.preset_config.get("algorithm", "avg_wave")
                        temp_dir_1 = self._mkdtemp("ens_1_")
                        temp_dir_2 = self._mkdtemp("ens_2_")

                        # Pass 1
                        self.post_log(i18n.tr("status_ensemble_start") + i18n.tr("log_pass", num=1, model=self.preset_config['model_1']))
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
                        self.post_log(i18n.tr("status_ensemble_start") + i18n.tr("log_pass", num=2, model=self.preset_config['model_2']))
                        separator.output_dir = temp_dir_2
                        separator.load_model(model_filename=self.preset_config["model_2"])
                        old_stderr = sys.stderr
                        sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                        try:
                            output_files_2 = separator.separate(safe_input_file)
                        finally:
                            sys.stderr = old_stderr

                        self.post_progress(0)
                        self.post_log(i18n.tr("status_ensemble_mixing"))
                        
                        final_outputs = []
                        # Stems in both M1 and M2
                        for f1 in output_files_1:
                            stem1 = stem_from_filename(f1)
                            clean_ext = os.path.splitext(f1)[1]
                            f2 = next((f for f in output_files_2 if stem_from_filename(f) == stem1), None)
                            if f2:
                                p1 = os.path.join(temp_dir_1, f1)
                                p2 = os.path.join(temp_dir_2, f2)
                                mixed, sr1 = blend_audio(p1, p2, algorithm)
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
                            if not any(stem_from_filename(f) == stem2 for f in output_files_1):
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

                    else:
                        # ====== CHAINED PRESET MULTI-PASS (Supports N passes) ======
                        final_outputs = []

                        # Collect all models in order from preset_config or manual models
                        chain_steps = []
                        step_idx = 1
                        while True:
                            model_key = f"model_{step_idx}"
                            m_name = self.preset_config.get(model_key) if self.preset_config else None
                            if not m_name:
                                if step_idx == 1:
                                    m_name = self.model_name
                                elif step_idx == 2:
                                    m_name = self.model_name_2
                                elif step_idx == 3:
                                    m_name = self.model_name_3
                                elif step_idx == 4:
                                    m_name = self.model_name_4
                                elif step_idx == 5:
                                    m_name = getattr(self, "model_name_5", None)
                            
                            if not m_name:
                                break

                            pass_key = "pass_stem" if step_idx == 1 else f"pass_stem_{step_idx}"
                            p_stem = self.preset_config.get(pass_key, "").lower() if self.preset_config else ""
                            rename_map = self.preset_config.get(f"m{step_idx}_rename_map", {}) if self.preset_config else {}
                            keep_name = self.preset_config.get(f"m{step_idx}_keep_name") if self.preset_config else None
                            keep_pass_stem = self.preset_config.get(f"m{step_idx}_keep_pass_stem_name") if self.preset_config else None
                            gain_db = float(self.preset_config.get(f"m{step_idx}_gain_db", 0.0)) if self.preset_config else 0.0

                            chain_steps.append({
                                "step_num": step_idx,
                                "model": m_name,
                                "pass_stem": p_stem,
                                "rename_map": rename_map,
                                "keep_name": keep_name,
                                "keep_pass_stem_name": keep_pass_stem,
                                "gain_db": gain_db
                            })
                            step_idx += 1

                        current_pass_file = safe_input_file
                        for i, step in enumerate(chain_steps):
                            step_num = step["step_num"]
                            model_file = step["model"]
                            pass_stem = step["pass_stem"]
                            rename_map = step["rename_map"]
                            keep_name = step["keep_name"]
                            keep_pass_stem_name = step["keep_pass_stem_name"]
                            gain_db = step.get("gain_db", 0.0)
                            is_last_step = (i == len(chain_steps) - 1)

                            def _copy_with_gain(src, dst, g):
                                if g != 0.0:
                                    try:
                                        d_arr, d_sr = sf.read(src, dtype='float32')
                                        d_arr = d_arr * (10.0 ** (g / 20.0))
                                        sf.write(dst, d_arr, d_sr)
                                        return
                                    except Exception:
                                        pass
                                shutil.copy(src, dst)

                            temp_dir = self._mkdtemp(f"chain_{step_num}_")
                            self.post_progress(0)
                            self.post_log(i18n.tr("status_ensemble_start") + i18n.tr("log_pass", num=step_num, model=model_file))
                            separator.output_dir = temp_dir
                            separator.load_model(model_filename=model_file)

                            old_stderr = sys.stderr
                            sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                            try:
                                step_output_files = separator.separate(current_pass_file)
                            finally:
                                sys.stderr = old_stderr

                            next_pass_file = None
                            for f in step_output_files:
                                stem = stem_from_filename(f)
                                clean_ext = os.path.splitext(f)[1]
                                stem_match = (pass_stem != "" and stems_are_equivalent(stem, pass_stem))
                                found_map, suffix = get_rename_suffix(stem, rename_map) if rename_map else (False, None)

                                if stem_match and not is_last_step:
                                    next_pass_file = os.path.join(temp_dir, f)

                                if stem_match and keep_pass_stem_name:
                                    suffix_clean = keep_pass_stem_name.lstrip('_')
                                    out_name = f"{folder_name}_{suffix_clean}{clean_ext}" if not self.use_subfolder else f"{suffix_clean}{clean_ext}"
                                    final_path = os.path.join(file_output_dir, out_name)
                                    _copy_with_gain(os.path.join(temp_dir, f), final_path, gain_db)
                                    final_outputs.append(out_name)
                                    continue

                                if rename_map:
                                    if found_map and suffix is None:
                                        # Explicitly discarded stem
                                        continue
                                    if suffix is not None:
                                        suffix_clean = suffix.lstrip('_')
                                        out_name = f"{folder_name}_{suffix_clean}{clean_ext}" if not self.use_subfolder else f"{suffix_clean}{clean_ext}"
                                        final_path = os.path.join(file_output_dir, out_name)
                                        _copy_with_gain(os.path.join(temp_dir, f), final_path, gain_db)
                                        final_outputs.append(out_name)
                                else:
                                    if not stem_match or is_last_step:
                                        def_keep = keep_name if keep_name else f"_{stem.capitalize()}"
                                        suffix_clean = def_keep.lstrip('_')
                                        out_name = f"{folder_name}_{suffix_clean}{clean_ext}" if not self.use_subfolder else f"{suffix_clean}{clean_ext}"
                                        final_path = os.path.join(file_output_dir, out_name)
                                        _copy_with_gain(os.path.join(temp_dir, f), final_path, gain_db)
                                        final_outputs.append(out_name)

                            # Handle fallback if pass stem was not matched exactly
                            if pass_stem and not next_pass_file and not is_last_step and step_output_files:
                                sec_group = {"other", "instrumental", "noise", "reverb", "no_dry", "nodry", "bleed", "extra"}
                                if len(step_output_files) == 2:
                                    if pass_stem in sec_group:
                                        next_pass_file = os.path.join(temp_dir, step_output_files[1])
                                    else:
                                        next_pass_file = os.path.join(temp_dir, step_output_files[0])
                                else:
                                    next_pass_file = os.path.join(temp_dir, step_output_files[0])
                                self.post_log(i18n.tr("log_fallback_stem", file=os.path.basename(next_pass_file), stem=pass_stem))

                            if not is_last_step:
                                if not next_pass_file:
                                    self.post_log(i18n.tr("log_missing_pass_stem", stem=pass_stem))
                                    break
                                # Save next_pass_file to a safe persistent temp path for the next step before temp_dir is removed
                                persistent_next_pass = os.path.join(tempfile.gettempdir(), f"chain_pass_{uuid.uuid4().hex[:8]}.wav")
                                shutil.copy2(next_pass_file, persistent_next_pass)
                                current_pass_file = persistent_next_pass

                            shutil.rmtree(temp_dir, ignore_errors=True)

                        # Post-mix rules (e.g. summing stems or subtracting vocals from input mix)
                        post_mix_rules = self.preset_config.get("post_mix", []) if self.preset_config else []
                        for pm_rule in post_mix_rules:
                            out_suffix = pm_rule.get("output", "")
                            if not out_suffix:
                                continue

                            if pm_rule.get("subtract_from_input"):
                                stems_to_sub = pm_rule.get("subtract_stems", [])
                                try:
                                    sub_data, in_sr = sf.read(safe_input_file, dtype='float32')
                                    for stem_key in stems_to_sub:
                                        clean_key = stem_key.lstrip('_')
                                        match_file = next((f for f in final_outputs if os.path.splitext(f)[0] in (f"{folder_name}_{clean_key}", clean_key)), None)
                                        if match_file:
                                            full_p = os.path.join(file_output_dir, match_file)
                                            data, _ = sf.read(full_p, dtype='float32')
                                            if sub_data.ndim == 2 and data.ndim == 1:
                                                data = np.tile(data[:, None], (1, sub_data.shape[1]))
                                            elif sub_data.ndim == 1 and data.ndim == 2:
                                                sub_data = np.tile(sub_data[:, None], (1, data.shape[1]))
                                            min_len = min(len(sub_data), len(data))
                                            sub_data[:min_len] -= data[:min_len]

                                    out_sfx_clean = out_suffix.lstrip('_')
                                    out_mix_name = f"{folder_name}_{out_sfx_clean}.wav" if not self.use_subfolder else f"{out_sfx_clean}.wav"
                                    out_mix_path = os.path.join(file_output_dir, out_mix_name)
                                    sf.write(out_mix_path, sub_data, in_sr)
                                    if out_mix_name not in final_outputs:
                                        final_outputs.append(out_mix_name)
                                except Exception as sub_err:
                                    self.post_log(f"Error computing subtraction instrumental: {sub_err}")

                            else:
                                stems_to_mix = pm_rule.get("stems", [])
                                delete_sources = pm_rule.get("delete_sources", [])
                                if not stems_to_mix:
                                    continue

                                mixed_audio = None
                                mix_sr = None
                                found_paths = []
                                for stem_key in stems_to_mix:
                                    clean_key = stem_key.lstrip('_')
                                    match_file = next((f for f in final_outputs if os.path.splitext(f)[0] in (f"{folder_name}_{clean_key}", clean_key)), None)
                                    if match_file:
                                        full_p = os.path.join(file_output_dir, match_file)
                                        found_paths.append((stem_key, match_file, full_p))
                                        try:
                                            data, sr = sf.read(full_p, dtype='float32')
                                            if mix_sr is None:
                                                mix_sr = sr
                                            if mixed_audio is None:
                                                mixed_audio = data
                                            else:
                                                if mixed_audio.ndim == 1 and data.ndim == 2:
                                                    mixed_audio = np.tile(mixed_audio[:, None], (1, data.shape[1]))
                                                elif mixed_audio.ndim == 2 and data.ndim == 1:
                                                    data = np.tile(data[:, None], (1, mixed_audio.shape[1]))
                                                min_len = min(len(mixed_audio), len(data))
                                                mixed_audio = mixed_audio[:min_len] + data[:min_len]
                                        except Exception as mix_err:
                                            self.post_log(f"Error reading {match_file} for post-mixing: {mix_err}")

                                if mixed_audio is not None and mix_sr is not None:
                                    out_sfx_clean = out_suffix.lstrip('_')
                                    out_mix_name = f"{folder_name}_{out_sfx_clean}.wav" if not self.use_subfolder else f"{out_sfx_clean}.wav"
                                    out_mix_path = os.path.join(file_output_dir, out_mix_name)
                                    sf.write(out_mix_path, mixed_audio, mix_sr)
                                    if out_mix_name not in final_outputs:
                                        final_outputs.append(out_mix_name)

                                    # Cleanup deleted sources if requested
                                    for del_key in delete_sources:
                                        del_clean = del_key.lstrip('_')
                                        to_del = [item for item in found_paths if item[0] == del_key or os.path.splitext(item[1])[0] in (f"{folder_name}_{del_clean}", del_clean)]
                                        for _, df_name, df_path in to_del:
                                            if os.path.exists(df_path) and df_path != out_mix_path:
                                                try:
                                                    os.remove(df_path)
                                                except Exception:
                                                    pass
                                            if df_name in final_outputs:
                                                final_outputs.remove(df_name)

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
                    algorithm = self.ensemble_algorithm
                    temp_dir_1 = self._mkdtemp("ens_1_")
                    temp_dir_2 = self._mkdtemp("ens_2_")
                    base_input_name = os.path.splitext(os.path.basename(current_input_file))[0]

                    # Pass 1
                    self.post_log(i18n.tr("status_ensemble_start") + i18n.tr("log_pass", num=1, model=self.model_name))
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
                    self.post_log(i18n.tr("status_ensemble_start") + i18n.tr("log_pass", num=2, model=self.model_name_2))
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
            
                if safe_input_file and os.path.exists(safe_input_file):
                    try:
                        os.remove(safe_input_file)
                    except Exception:
                        pass

                # --- Silent stem detection and optional deletion (executed BEFORE format conversion) ---
                if self.delete_silent_stems and output_files:
                    surviving = []
                    for fname in output_files:
                        fpath = os.path.join(file_output_dir, fname) if not os.path.isabs(fname) else fname
                        if not os.path.exists(fpath):
                            surviving.append(fname)
                            continue

                        peak_db, rms_db = get_audio_volume_stats(fpath)
                        # A stem is silent if its peak is below the threshold OR if its average RMS energy is deeply in the noise floor
                        # (e.g. inactive stem with a single 1-sample transient artifact)
                        is_silent = (peak_db < self.silent_stem_threshold) or (rms_db < (self.silent_stem_threshold - 10.0))

                        display_name = os.path.basename(fname)
                        if is_silent:
                            try:
                                os.remove(fpath)
                                self.post_log(i18n.tr("status_silent_stem_deleted", file=display_name, peak=peak_db, rms=rms_db, threshold=self.silent_stem_threshold))
                            except Exception as del_err:
                                self.post_log(f"Error removing silent file {display_name}: {del_err}")
                                surviving.append(fname)
                        else:
                            self.post_log(i18n.tr("status_silent_stem_kept", file=display_name, peak=peak_db, rms=rms_db, threshold=self.silent_stem_threshold))
                            surviving.append(fname)
                    output_files = surviving

                # --- Format conversion (runs only on active/surviving stems) ---
                if self.output_format == "WAV":
                    bd_str = str(self.bit_depth).lower()
                    if "16" in bd_str or "24" in bd_str:
                        codec = "pcm_s16le" if "16" in bd_str else "pcm_s24le"
                        target_bd = "16-bit" if "16" in bd_str else "24-bit"
                        for file in output_files:
                            try:
                                fpath = os.path.join(file_output_dir, file)
                                tmp_path = os.path.join(file_output_dir, f"tmp_{file}")
                                self.post_log(i18n.tr("status_converting", file=file, format=f"WAV ({target_bd})"))
                                cmd = ["ffmpeg", "-y", "-i", fpath, "-c:a", codec, tmp_path]
                                result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                if result.returncode == 0 and os.path.exists(tmp_path):
                                    os.replace(tmp_path, fpath)
                                else:
                                    if os.path.exists(tmp_path):
                                        os.remove(tmp_path)
                            except Exception as ex:
                                self.post_log(i18n.tr("log_convert_error", file=file, error=ex))

                elif self.output_format in ("FLAC", "MP3"):
                    new_files = []
                    for file in output_files:
                        try:
                            old_path = os.path.join(file_output_dir, file)
                            base, _ = os.path.splitext(file)
                            new_ext = f".{self.output_format.lower()}"
                            new_filename = f"{base}{new_ext}"
                            new_path = os.path.join(file_output_dir, new_filename)
                        
                            if self.output_format == "FLAC":
                                bd_str = str(self.bit_depth).lower()
                                sample_fmt = "s16" if "16" in bd_str else "s32"
                                target_bd = "16-bit" if "16" in bd_str else "24-bit"
                                self.post_log(i18n.tr("status_converting", file=file, format=f"FLAC ({target_bd})"))
                                cmd = ["ffmpeg", "-y", "-i", old_path, "-c:a", "flac", "-sample_fmt", sample_fmt, new_path]
                            else: # MP3
                                import re
                                mp3_b = re.sub(r'[^0-9]', '', str(self.bitrate))
                                b_arg = f"{mp3_b}k" if mp3_b else "320k"
                                self.post_log(i18n.tr("status_converting", file=file, format=f"MP3 ({b_arg})"))
                                cmd = ["ffmpeg", "-y", "-i", old_path, "-c:a", "libmp3lame", "-b:a", b_arg, new_path]
                            
                            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                            if result.returncode == 0:
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                                new_files.append(new_filename)
                            else:
                                self.post_log(i18n.tr("log_ffmpeg_failed", file=file))
                                new_files.append(file)
                        except Exception as ex:
                            self.post_log(i18n.tr("log_convert_error", file=file, error=ex))
                            new_files.append(file)
                    output_files = new_files

                # Accumulate final output paths
                for fname in output_files:
                    fpath = os.path.join(file_output_dir, fname) if not os.path.isabs(fname) else fname
                    if os.path.exists(fpath):
                        self.all_output_files.append(fpath)

            self.post_progress(100)
            self.post_log(i18n.tr("status_complete", files=output_files))
            if self.on_done:
                try:
                    self.on_done(True, i18n.tr("msg_success"), self.all_output_files)
                except Exception:
                    pass
            if self.parent:
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
                if self.on_done:
                    try:
                        self.on_done(False, friendly, [])
                    except Exception:
                        pass
                if self.parent:
                    wx.PostEvent(self.parent, DoneEvent(False, friendly))
            else:
                self.post_log(i18n.tr("status_error", error=error_msg))
                if self.on_done:
                    try:
                        self.on_done(False, error_msg, [])
                    except Exception:
                        pass
                if self.parent:
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
            
            # Restore the library patches applied during this run
            if 'patcher' in locals():
                try:
                    patcher.restore()
                except Exception:
                    pass

            # Remove temp dirs and the converted input WAV left behind by an
            # error path (normally cleaned per-file, but failures skip that code).
            for path in self._temp_dirs:
                shutil.rmtree(path, ignore_errors=True)
            self._temp_dirs = []
            try:
                if 'safe_input_file' in locals() and os.path.exists(safe_input_file):
                    os.remove(safe_input_file)
            except Exception:
                pass

    def _mkdtemp(self, prefix):
        # Tracked so run()'s finally can remove leftovers when separation fails
        # mid-way (e.g. OOM), instead of leaving dirs in the output folder.
        path = tempfile.mkdtemp(dir=self.output_dir, prefix=prefix)
        self._temp_dirs.append(path)
        return path

    def post_progress(self, value, maximum=100):
        if self.on_progress:
            try:
                self.on_progress(value, maximum)
            except Exception:
                pass
        if self.parent:
            wx.PostEvent(self.parent, ProgressEvent(value, maximum))

    def post_log(self, message):
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass
        if self.parent:
            wx.PostEvent(self.parent, LogEvent(message))

    def stop(self):
        self._stop_event.set()
