import wx
import threading
import logging
import os
import subprocess
from audio_separator.separator import Separator
from gui.i18n_manager import i18n

import re
import sys

# Custom event for updating the log in the UI
EVT_LOG_ID = wx.NewIdRef()
EVT_DONE_ID = wx.NewIdRef()
EVT_PROGRESS_ID = wx.NewIdRef()

class ProgressEvent(wx.PyEvent):
    def __init__(self, value, maximum=100):
        super().__init__()
        self.SetEventType(EVT_PROGRESS_ID)
        self.value = value
        self.maximum = maximum

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

class LogEvent(wx.PyEvent):
    def __init__(self, message):
        super().__init__()
        self.SetEventType(EVT_LOG_ID)
        self.message = message

class DoneEvent(wx.PyEvent):
    def __init__(self, success, message):
        super().__init__()
        self.SetEventType(EVT_DONE_ID)
        self.success = success
        self.message = message

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
    def __init__(self, parent, input_file, output_dir, model_name, use_gpu=True, output_format="WAV", model_name_2=None, preset_config=None, ensemble_algorithm="avg_wave"):
        super().__init__()
        self.parent = parent
        self.input_file = input_file
        self.output_dir = output_dir
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.output_format = output_format
        self.model_name_2 = model_name_2
        self.preset_config = preset_config
        self.ensemble_algorithm = ensemble_algorithm
        self._stop_event = threading.Event()

    def run(self):
        try:
            # GPU/CPU enforcement logic
            old_cuda_env = os.environ.get('CUDA_VISIBLE_DEVICES')
            if not self.use_gpu:
                os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
                import torch
                self._old_is_available = torch.cuda.is_available
                torch.cuda.is_available = lambda: False
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
            
            separator = Separator(
                log_level=logging.INFO,
                model_file_dir=os.path.join(os.getcwd(), 'models'),
                output_dir=self.output_dir
            )

            if self.preset_config:
                preset_type = self.preset_config.get("type", "chain")

                if preset_type == "ensemble":
                    # ====== PRESET ENSEMBLE (2-Pass + Local Mixing) ======
                    import tempfile
                    import shutil
                    import soundfile as sf
                    import numpy as np
                    import re

                    algorithm = self.preset_config.get("algorithm", "avg_wave")
                    temp_dir_1 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_1_")
                    temp_dir_2 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_2_")
                    base_input_name = os.path.splitext(os.path.basename(self.input_file))[0]

                    def get_stem_clean_ens(filename):
                        matches = re.findall(r"_\((.*?)\)_", filename)
                        if matches:
                            s = matches[-1].lower()
                        else:
                            base = os.path.splitext(filename)[0]
                            parts = base.split("_")
                            s = parts[-1].lower() if parts else base.lower()
                        return "instrumental" if s == "other" else s

                    def blend(a, b, algo):
                        if algo == "min_wave":
                            return np.minimum(a, b)
                        elif algo == "max_wave":
                            return np.maximum(a, b)
                        elif algo == "median_wave":
                            return np.median(np.stack([a, b]), axis=0)
                        else:  # avg_wave (default)
                            return (a + b) / 2.0

                    # Pass 1
                    self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 1: {self.preset_config['model_1']})")
                    separator.output_dir = temp_dir_1
                    separator.load_model(model_filename=self.preset_config["model_1"])
                    old_stderr = sys.stderr
                    sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                    try:
                        output_files_1 = separator.separate(self.input_file)
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
                        output_files_2 = separator.separate(self.input_file)
                    finally:
                        sys.stderr = old_stderr

                    # Blending
                    self.post_log(i18n.tr("status_ensemble_mixing") + f" [{algorithm}]")
                    final_outputs = []
                    for f1 in output_files_1:
                        stem1 = get_stem_clean_ens(f1)
                        match_2 = [f for f in output_files_2 if get_stem_clean_ens(f) == stem1]
                        clean_ext = os.path.splitext(f1)[1]
                        if match_2:
                            d1, sr1 = sf.read(os.path.join(temp_dir_1, f1))
                            d2, _ = sf.read(os.path.join(temp_dir_2, match_2[0]))
                            min_len = min(len(d1), len(d2))
                            mixed = blend(d1[:min_len], d2[:min_len], algorithm)
                            out_name = f"{base_input_name}_(Ensemble_{stem1.capitalize()}){clean_ext}"
                            sf.write(os.path.join(self.output_dir, out_name), mixed, sr1)
                            final_outputs.append(out_name)
                        else:
                            out_name = f"{base_input_name}_(Ensemble_{stem1.capitalize()}_M1){clean_ext}"
                            shutil.copy(os.path.join(temp_dir_1, f1), os.path.join(self.output_dir, out_name))
                            final_outputs.append(out_name)

                    shutil.rmtree(temp_dir_1, ignore_errors=True)
                    shutil.rmtree(temp_dir_2, ignore_errors=True)
                    output_files = final_outputs
                    self.post_log(i18n.tr("status_ensemble_done"))

                else:
                    # ====== CHAINED PRESET MULTI-PASS ======
                    import tempfile
                    import shutil
                    import re

                    temp_dir_1 = tempfile.mkdtemp(dir=self.output_dir, prefix="chain_1_")
                    temp_dir_2 = tempfile.mkdtemp(dir=self.output_dir, prefix="chain_2_")
                    
                    base_input_name = os.path.splitext(os.path.basename(self.input_file))[0]
                    final_outputs = []
                    
                    def get_stem_clean(filename):
                        matches = re.findall(r"_\((.*?)\)_", filename)
                        if matches:
                            stem = matches[-1].lower()
                        else:
                            base = os.path.splitext(filename)[0]
                            parts = base.split("_")
                            stem = parts[-1].lower() if parts else base.lower()
                        return stem
                    
                    # Model 1
                    self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 1: {self.preset_config['model_1']})")
                    separator.output_dir = temp_dir_1
                    separator.load_model(model_filename=self.preset_config['model_1'])
                    
                    old_stderr = sys.stderr
                    sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                    try:
                        output_files_1 = separator.separate(self.input_file)
                    finally:
                        sys.stderr = old_stderr

                    pass_file_path = None
                    pass_stem = self.preset_config["pass_stem"].lower()
                    
                    for f1 in output_files_1:
                        stem1 = get_stem_clean(f1)
                        clean_ext = os.path.splitext(f1)[1]
                        
                        # Tratta 'other' e 'instrumental' come sinonimi per la decisione di quale stelo passare al M2
                        stem_match = (stem1 == pass_stem) or (stem1 in ["other", "instrumental"] and pass_stem in ["other", "instrumental"])
                        
                        if stem_match:
                            pass_file_path = os.path.join(temp_dir_1, f1)
                            if "m1_keep_pass_stem_name" in self.preset_config:
                                suffix = self.preset_config["m1_keep_pass_stem_name"]
                                out_name = f"{base_input_name}{suffix}{clean_ext}"
                                final_path = os.path.join(self.output_dir, out_name)
                                shutil.copy(os.path.join(temp_dir_1, f1), final_path)
                                final_outputs.append(out_name)
                        else:
                            suffix = self.preset_config.get("m1_keep_name", "_Instrumental")
                            out_name = f"{base_input_name}{suffix}{clean_ext}"
                            final_path = os.path.join(self.output_dir, out_name)
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
                            
                        for f2 in output_files_2:
                            stem2 = get_stem_clean(f2)
                            clean_ext = os.path.splitext(f2)[1]
                            
                            rename_map = self.preset_config.get("m2_rename_map", {})
                            if stem2 in rename_map:
                                suffix = rename_map[stem2]
                                if not suffix:  # If mapped to None or "", discard the stem
                                    continue
                            else:
                                suffix = f"_{stem2.capitalize()}"
                                
                            out_name = f"{base_input_name}{suffix}{clean_ext}"
                            final_path = os.path.join(self.output_dir, out_name)
                            shutil.copy(os.path.join(temp_dir_2, f2), final_path)
                            final_outputs.append(out_name)
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
                self.post_log(i18n.tr("status_starting", file=os.path.basename(self.input_file)))
                
                old_stderr = sys.stderr
                sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                try:
                    output_files = separator.separate(self.input_file)
                finally:
                    sys.stderr = old_stderr
            else:
                # ====== ENSEMBLE DUAL MODEL PASS (2-Pass + Local Mixing) ======
                import tempfile
                import shutil
                import soundfile as sf
                import numpy as np
                import re

                algorithm = self.ensemble_algorithm
                temp_dir_1 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_1_")
                temp_dir_2 = tempfile.mkdtemp(dir=self.output_dir, prefix="ens_2_")
                base_input_name = os.path.splitext(os.path.basename(self.input_file))[0]

                def get_stem_clean_m(filename):
                    matches = re.findall(r"_\((.*?)\)_", filename)
                    if matches:
                        s = matches[-1].lower()
                    else:
                        base = os.path.splitext(filename)[0]
                        parts = base.split("_")
                        s = parts[-1].lower() if parts else base.lower()
                    return "instrumental" if s == "other" else s

                def blend_m(a, b, algo):
                    if algo == "min_wave":
                        return np.minimum(a, b)
                    elif algo == "max_wave":
                        return np.maximum(a, b)
                    elif algo == "median_wave":
                        return np.median(np.stack([a, b]), axis=0)
                    else:  # avg_wave (default)
                        return (a + b) / 2.0

                # Pass 1
                self.post_log(i18n.tr("status_ensemble_start") + f" (Pass 1: {self.model_name})")
                separator.output_dir = temp_dir_1
                separator.load_model(model_filename=self.model_name)
                old_stderr = sys.stderr
                sys.stderr = TqdmCaptureStream(self.post_progress, old_stderr)
                try:
                    output_files_1 = separator.separate(self.input_file)
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
                    output_files_2 = separator.separate(self.input_file)
                finally:
                    sys.stderr = old_stderr

                # Blending
                self.post_log(i18n.tr("status_ensemble_mixing") + f" [{algorithm}]")
                final_outputs = []
                for f1 in output_files_1:
                    stem1 = get_stem_clean_m(f1)
                    match_2 = [f for f in output_files_2 if get_stem_clean_m(f) == stem1]
                    clean_ext = os.path.splitext(f1)[1]
                    if match_2:
                        d1, sr1 = sf.read(os.path.join(temp_dir_1, f1))
                        d2, _ = sf.read(os.path.join(temp_dir_2, match_2[0]))
                        min_len = min(len(d1), len(d2))
                        mixed = blend_m(d1[:min_len], d2[:min_len], algorithm)
                        out_name = f"{base_input_name}_(Ensemble_{stem1.capitalize()}){clean_ext}"
                        sf.write(os.path.join(self.output_dir, out_name), mixed, sr1)
                        final_outputs.append(out_name)
                    else:
                        out_name = f"{base_input_name}_(Ensemble_{stem1.capitalize()}_M1){clean_ext}"
                        shutil.copy(os.path.join(temp_dir_1, f1), os.path.join(self.output_dir, out_name))
                        final_outputs.append(out_name)
                # Stems only in M2
                for f2 in output_files_2:
                    stem2 = get_stem_clean_m(f2)
                    if not any(get_stem_clean_m(f) == stem2 for f in output_files_1):
                        clean_ext = os.path.splitext(f2)[1]
                        out_name = f"{base_input_name}_(Ensemble_{stem2.capitalize()}_M2){clean_ext}"
                        shutil.copy(os.path.join(temp_dir_2, f2), os.path.join(self.output_dir, out_name))
                        final_outputs.append(out_name)

                shutil.rmtree(temp_dir_1, ignore_errors=True)
                shutil.rmtree(temp_dir_2, ignore_errors=True)
                output_files = final_outputs
                self.post_log(i18n.tr("status_ensemble_done"))
            
            if self.output_format != "WAV":
                new_files = []
                for file in output_files:
                    try:
                        old_path = os.path.join(self.output_dir, file)
                        base, _ = os.path.splitext(file)
                        new_ext = f".{self.output_format.lower()}"
                        new_filename = f"{base}{new_ext}"
                        new_path = os.path.join(self.output_dir, new_filename)
                        
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
            
            self.post_progress(100)
            self.post_log(i18n.tr("status_complete", files=output_files))
            wx.PostEvent(self.parent, DoneEvent(True, i18n.tr("msg_success")))

        except Exception as e:
            error_msg = str(e)
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
                except ImportError:
                    pass
                
                try:
                    import onnxruntime
                    if hasattr(self, '_old_get_providers'):
                        onnxruntime.get_available_providers = self._old_get_providers
                except ImportError:
                    pass

    def post_progress(self, value, maximum=100):
        wx.PostEvent(self.parent, ProgressEvent(value, maximum))

    def post_log(self, message):
        wx.PostEvent(self.parent, LogEvent(message))

    def stop(self):
        self._stop_event.set()
