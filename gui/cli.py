import sys
import os
import re
import glob
import time
import argparse
import logging
from typing import List, Optional, Tuple, Dict, Any

from gui.version import __version__, get_edition
from gui.utils import get_app_data_dir, download_file
from gui.i18n_manager import i18n
from gui.model_manager import ModelManager
from gui.preset_manager import PresetManager
from gui.worker import SeparationThread

SUPPORTED_EXTENSIONS = {
    '.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg',
    '.opus', '.wma', '.aiff', '.aif', '.alac', '.mp4',
    '.mkv', '.avi', '.mov'
}

class CliProgress:
    """Terminal progress reporter with fallback for non-interactive streams."""
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.last_val = -1
        self.is_tty = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False

    def on_progress(self, value: int, maximum: int = 100):
        if self.quiet:
            return
        percent = int((value / maximum) * 100) if maximum > 0 else value
        if percent == self.last_val:
            return
        self.last_val = percent

        bar_len = 30
        filled = int((percent / 100.0) * bar_len)
        bar = '=' * filled + '-' * (bar_len - filled)
        
        if self.is_tty:
            sys.stdout.write(f"\rProgress: [{bar}] {percent}%")
            sys.stdout.flush()
            if percent >= 100:
                sys.stdout.write("\n")
                sys.stdout.flush()
        else:
            if percent in (0, 25, 50, 75, 100) or percent % 20 == 0:
                print(f"Progress: {percent}%")

    def on_log(self, message: str):
        if not self.quiet:
            # Clear progress line if tty
            if self.is_tty and self.last_val >= 0 and self.last_val < 100:
                sys.stdout.write("\r\033[K")
            print(f"[INFO] {message}")


def collect_audio_files(paths: List[str], recursive: bool = False) -> List[str]:
    """Expands files, directories, and glob patterns into a list of absolute file paths."""
    found_files = []
    for p in paths:
        if any(char in p for char in ['*', '?', '[']):
            matched = glob.glob(p, recursive=recursive)
            for m in matched:
                if os.path.isfile(m) and os.path.splitext(m)[1].lower() in SUPPORTED_EXTENSIONS:
                    found_files.append(os.path.abspath(m))
        elif os.path.isdir(p):
            if recursive:
                for root, _, filenames in os.walk(p):
                    for f in filenames:
                        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                            found_files.append(os.path.abspath(os.path.join(root, f)))
            else:
                for f in os.listdir(p):
                    full = os.path.join(p, f)
                    if os.path.isfile(full) and os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                        found_files.append(os.path.abspath(full))
        elif os.path.isfile(p):
            if os.path.splitext(p)[1].lower() in SUPPORTED_EXTENSIONS:
                found_files.append(os.path.abspath(p))
            else:
                print(f"[WARNING] Skipping unsupported file format: {p}")
        else:
            print(f"[WARNING] Input path not found: {p}")

    # Remove duplicates preserving order
    unique_files = []
    seen = set()
    for f in found_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    return unique_files


def resolve_model(model_manager: ModelManager, query: str) -> Optional[str]:
    """Finds exact model filename from a friendly name, alias, or direct filename."""
    if not query:
        return None
        
    query_clean = query.strip()
    
    # 1. Exact match in downloadable_models_by_file
    if query_clean in model_manager.downloadable_models_by_file:
        return query_clean
        
    # 2. Exact match in friendly names (case-insensitive)
    for friendly, data in model_manager.downloadable_models.items():
        if friendly.lower() == query_clean.lower():
            return friendly
            
    # 3. Exact match in aliases
    for alias, data in model_manager.downloadable_aliases.items():
        if alias.lower() == query_clean.lower():
            return alias
            
    # 4. Partial match in friendly names (e.g. "Viperx-1297", "Kim | Inst V1")
    for friendly in model_manager.downloadable_models.keys():
        if query_clean.lower() in friendly.lower():
            return friendly

    # 5. Partial match in aliases
    for alias in model_manager.downloadable_aliases.keys():
        if query_clean.lower() in alias.lower():
            return alias

    # 6. Partial match in filenames (e.g. "Inst_HQ_5" -> "UVR-MDX-NET-Inst_HQ_5.onnx")
    for filename in model_manager.downloadable_models_by_file.keys():
        if query_clean.lower() in filename.lower():
            return filename
            
    # Fallback to as-is (e.g. custom user model file or direct path)
    return query_clean


def resolve_preset(preset_name: str) -> Tuple[Optional[str], Optional[dict]]:
    """Resolves a preset key or custom name to (preset_key, preset_config)."""
    PresetManager.load_custom_presets()
    query = preset_name.strip()
    
    # 1. Exact preset_key match
    if query in PresetManager.presets_config:
        return query, PresetManager.presets_config[query]
        
    # 2. Key without 'preset_' prefix (e.g. 'vocal_split')
    alt_key = f"preset_{query}"
    if alt_key in PresetManager.presets_config:
        return alt_key, PresetManager.presets_config[alt_key]
        
    # 3. Custom preset key or friendly display name
    for key, config in PresetManager.presets_config.items():
        name = config.get("name", "")
        if name and name.lower() == query.lower():
            return key, config
        if key.lower() == query.lower() or key.replace("custom_", "").lower() == query.lower():
            return key, config
            
    return None, None


def ensure_model_downloaded(model_manager: ModelManager, model_filename: str, quiet: bool = False) -> bool:
    """Checks if the model is downloaded; if not, downloads it with a progress indicator."""
    if not model_filename:
        return True
        
    local_path = os.path.join(model_manager.models_dir, model_filename)
    if os.path.exists(local_path):
        return True

    file_info = model_manager.downloadable_models_by_file.get(model_filename)
    if not file_info:
        # Check aliases or downloadable_models
        for _, data in model_manager.downloadable_models.items():
            if data.get("file") == model_filename:
                file_info = data
                break
                
    if not file_info or not file_info.get("download_url"):
        if os.path.exists(local_path):
            return True
        print(f"[ERROR] Model '{model_filename}' not found locally in {model_manager.models_dir} and no download URL is available.")
        return False

    url = file_info["download_url"]
    if not quiet:
        print(f"Downloading model '{model_filename}' from {url}...")

    def _dl_hook(bytes_so_far, total_size):
        if not quiet and total_size > 0:
            percent = int((bytes_so_far / total_size) * 100)
            if sys.stdout.isatty():
                sys.stdout.write(f"\rDownloading: {percent}% ({bytes_so_far // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                sys.stdout.flush()

    try:
        download_file(url, local_path, overwrite=True, progress_callback=_dl_hook)
        if not quiet and sys.stdout.isatty():
            sys.stdout.write("\n")
            sys.stdout.flush()
        print(f"[SUCCESS] Model '{model_filename}' downloaded successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download model '{model_filename}': {e}")
        return False


def parse_db_threshold(val):
    """Parses dB threshold value from string or number, e.g. '-50', '-50dB', -45."""
    if val is None:
        return -50.0
    try:
        cleaned = str(val).lower().replace("db", "").strip()
        num = float(cleaned)
        if num > 0:
            num = -num
        return num
    except Exception:
        raise argparse.ArgumentTypeError(f"Invalid dB threshold: '{val}'. Expected a value like -50, -45, -60.")


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="music-separator",
        description=f"Music Separator v{__version__} ({get_edition()}) - AI Audio Stem Separation CLI"
    )

    # Informational / Utility
    parser.add_argument("-v", "--version", action="version", version=f"Music Separator v{__version__} ({get_edition()})")
    parser.add_argument("-l", "--list-models", action="store_true", help="List all available AI separation models and their download status")
    parser.add_argument("--list-presets", action="store_true", help="List all built-in and custom presets")
    parser.add_argument("--download-model", metavar="MODEL", type=str, help="Download a specific model to the local catalog and exit")

    # Inputs & Outputs
    parser.add_argument("-i", "--input", nargs="+", help="Audio file(s), directory, or wildcard pattern to separate")
    parser.add_argument("-o", "--output-dir", default="output", help="Directory where separated stems will be saved (default: ./output)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Scan subdirectories recursively when input is a folder")
    parser.add_argument("--no-subfolder", action="store_true", help="Save stems directly into the output directory without creating a subfolder per track")
    parser.add_argument("--clean-names", action="store_true", help="Strip leading track numbers (e.g. '01 - ') from output folder names")
    parser.add_argument("--delete-silent-stems", action="store_true", help="Automatically remove output stems that contain only silence")
    parser.add_argument("--silent-stem-threshold", type=parse_db_threshold, default=-50.0, help="Threshold in dB below which a stem is considered silent (default: -50 dB)")

    # Model & Preset Configuration
    parser.add_argument("-m", "--model", help="Name, filename, or alias of the separation model (e.g. 'BS-Roformer-SW.ckpt')")
    parser.add_argument("-p", "--preset", help="Name or key of a built-in or custom preset (e.g. 'preset_vocal_split', 'Denoise + Vocals')")
    parser.add_argument("--export-presets", nargs="?", const="custom_presets_export.json", metavar="FILE", help="Export custom presets to a JSON file (default: custom_presets_export.json)")
    parser.add_argument("--import-presets", metavar="FILE", help="Import custom presets from a JSON file")
    parser.add_argument("--model-2", help="Secondary model for 2-pass manual chains or ensembles")
    parser.add_argument("--model-3", help="Third model for 3-pass manual chains or ensembles")
    parser.add_argument("--model-4", help="Fourth model for 4-pass manual chains or ensembles")
    parser.add_argument("--ensemble-algo", choices=["avg_wave", "median_wave", "min_wave", "max_wave"], default="avg_wave", help="Ensemble algorithm when multiple models are selected (default: avg_wave)")

    # Audio & Hardware Execution Settings
    parser.add_argument("--format", choices=["WAV", "FLAC", "MP3"], default="WAV", help="Output audio format (default: WAV)")
    parser.add_argument("--bit-depth", choices=["16", "24", "32", "16-bit", "24-bit", "32-bit Float"], default="24-bit", help="Bit depth for WAV and FLAC (default: 24-bit)")
    parser.add_argument("--bitrate", choices=["320k", "256k", "192k", "128k", "320", "256", "192", "128", "320 kbps", "256 kbps", "192 kbps", "128 kbps"], default="320k", help="Bitrate for MP3 (default: 320k)")
    parser.add_argument("--gpu", action="store_true", default=None, help="Force GPU acceleration (CUDA on Windows/Linux, MPS on Apple Silicon)")
    parser.add_argument("--cpu", action="store_true", default=None, help="Force CPU-only processing")
    parser.add_argument("--chunk-duration", type=int, default=None, help="Process audio in chunks of N seconds (reduces memory usage)")
    parser.add_argument("--preview", choices=["first", "final"], default=None, help="Process only a 30-second preview ('first' or 'final' 30 seconds)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimize terminal output (only print errors and results)")

    return parser


def run_cli(args_list: Optional[List[str]] = None) -> int:
    """Main CLI entry point. Returns exit code (0 for success, 1 for error)."""
    parser = build_parser()
    args = parser.parse_args(args_list)

    model_manager = ModelManager()
    # Wait for models catalog initialization (timeout 10s)
    model_manager._ready_event.wait(timeout=10)

    # 1. Action: List Models
    if args.list_models:
        print(f"\n--- Music Separator v{__version__} - Model Catalog ---")
        print(f"Models Directory: {model_manager.models_dir}\n")
        
        # Categorized listing
        downloaded_count = 0
        total_count = 0
        
        for category, models in model_manager.models_dict.items():
            print(f"[{category}]")
            for m in models:
                total_count += 1
                is_dl = model_manager.is_model_downloaded(m)
                if is_dl:
                    downloaded_count += 1
                status = "[Downloaded]" if is_dl else "[Available] "
                print(f"  {status} {m}")
            print()
            
        print(f"Summary: {downloaded_count}/{total_count} models downloaded locally.\n")
        return 0

    # 2. Action: List Presets
    if args.list_presets:
        PresetManager.load_custom_presets()
        print(f"\n--- Music Separator v{__version__} - Available Presets ---")
        print("\n[Built-in Presets]")
        for key in PresetManager.preset_keys:
            if not key.startswith("custom_") and key != "preset_none":
                display_name = PresetManager.get_preset_name(key, i18n)
                print(f"  - {key}  ({display_name})")
                
        custom_presets = [k for k in PresetManager.preset_keys if k.startswith("custom_")]
        if custom_presets:
            print("\n[Custom Presets]")
            for key in custom_presets:
                cfg = PresetManager.presets_config.get(key, {})
                name = cfg.get("name", key)
                ptype = cfg.get("type", "single")
                print(f"  - {name}  [Key: {key}, Type: {ptype}]")
        else:
            print("\n[Custom Presets]\n  (No custom presets found in custom_presets.json)")
        print()
        return 0

    # 3. Action: Export Presets
    if args.export_presets:
        export_file = args.export_presets
        count, err = PresetManager.export_presets(export_file)
        if count > 0:
            print(f"[SUCCESS] Exported {count} custom preset(s) to '{export_file}'.")
            return 0
        else:
            print(f"[ERROR] Failed to export presets: {err}")
            return 1

    # 4. Action: Import Presets
    if args.import_presets:
        import_file = args.import_presets
        count, names, err = PresetManager.import_presets(import_file)
        if count > 0:
            names_str = ", ".join(names)
            print(f"[SUCCESS] Successfully imported {count} preset(s): {names_str}")
            return 0
        else:
            print(f"[ERROR] Failed to import presets from '{import_file}': {err}")
            return 1

    # 5. Action: Download Model
    if args.download_model:
        model_file = resolve_model(model_manager, args.download_model)
        if not model_file:
            print(f"[ERROR] Could not resolve model '{args.download_model}'.")
            return 1
        success = ensure_model_downloaded(model_manager, model_file, quiet=args.quiet)
        return 0 if success else 1

    # 4. Action: Separate Audio
    if not args.input:
        parser.print_help()
        print("\n[ERROR] Missing required input: Specify audio file(s) with -i / --input")
        return 1

    # Resolve input files
    input_files = collect_audio_files(args.input, recursive=args.recursive)
    if not input_files:
        print("[ERROR] No valid audio files found from the specified input(s).")
        return 1

    # Resolve model or preset
    preset_key = None
    preset_config = None
    model_1 = None
    model_2 = args.model_2
    model_3 = args.model_3
    model_4 = args.model_4

    if args.preset:
        preset_key, preset_config = resolve_preset(args.preset)
        if not preset_config:
            print(f"[ERROR] Preset '{args.preset}' not found. Use --list-presets to view available presets.")
            return 1
        if not args.quiet:
            print(f"Using Preset: {preset_config.get('name', preset_key)}")
            
        # Ensure all models required by the preset are downloaded
        models_to_check = []
        step_idx = 1
        while True:
            m_key = f"model_{step_idx}"
            if m_key not in preset_config:
                break
            models_to_check.append(preset_config[m_key])
            step_idx += 1
        if preset_config.get("model_name"):
            models_to_check.append(preset_config["model_name"])
            
        for m in models_to_check:
            resolved_m = resolve_model(model_manager, m)
            if not ensure_model_downloaded(model_manager, resolved_m, quiet=args.quiet):
                return 1
    else:
        # Single model or manual chain/ensemble
        chosen_model = args.model or "BS-Roformer-SW.ckpt"  # Default model
        model_1 = resolve_model(model_manager, chosen_model)
        if not model_1:
            print(f"[ERROR] Model '{chosen_model}' could not be resolved.")
            return 1
            
        models_to_download = [model_1]
        if model_2:
            model_2 = resolve_model(model_manager, model_2)
            models_to_download.append(model_2)
        if model_3:
            model_3 = resolve_model(model_manager, model_3)
            models_to_download.append(model_3)
        if model_4:
            model_4 = resolve_model(model_manager, model_4)
            models_to_download.append(model_4)

        for m in models_to_download:
            if not ensure_model_downloaded(model_manager, m, quiet=args.quiet):
                return 1

    # Hardware selection
    use_gpu = True
    if args.cpu:
        use_gpu = False
    elif args.gpu:
        use_gpu = True

    # Output directory
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if not args.quiet:
        print(f"\n=======================================================")
        print(f" Music Separator CLI v{__version__}")
        print(f"=======================================================")
        print(f"Files to process : {len(input_files)}")
        print(f"Output Directory : {output_dir}")
        print(f"Device           : {'GPU (CUDA/MPS)' if use_gpu else 'CPU'}")
        print(f"Output Format    : {args.format}")
        if preset_config:
            print(f"Pipeline         : Preset '{preset_config.get('name', preset_key)}'")
        else:
            print(f"Model            : {model_1}")
        print(f"=======================================================\n")

    # Set up progress and completion trackers
    progress_tracker = CliProgress(quiet=args.quiet)
    done_result = {"success": False, "message": "", "files": []}

    def _on_done(success: bool, message: str, files: List[str]):
        done_result["success"] = success
        done_result["message"] = message
        done_result["files"] = files

    # Create dummy parent context so AudioPatches and SeparationThread have model access
    class CliParentContext:
        def __init__(self, mm):
            self.model_manager = mm
            self.downloadable_models = mm.downloadable_models

    context = CliParentContext(model_manager)

    worker = SeparationThread(
        parent=None,
        input_files=input_files,
        output_dir=output_dir,
        model_name=model_1 or (preset_config.get("model_1") if preset_config else ""),
        use_gpu=use_gpu,
        output_format=args.format,
        model_name_2=model_2,
        model_name_3=model_3,
        model_name_4=model_4,
        preset_config=preset_config,
        ensemble_algorithm=args.ensemble_algo,
        chunk_duration=args.chunk_duration,
        remove_leading_numbers=args.clean_names,
        use_subfolder=not args.no_subfolder,
        delete_silent_stems=args.delete_silent_stems,
        silent_stem_threshold=args.silent_stem_threshold,
        enable_preview=bool(args.preview),
        preview_mode=args.preview or "first",
        bit_depth=args.bit_depth,
        bitrate=args.bitrate,
        on_progress=progress_tracker.on_progress,
        on_log=progress_tracker.on_log,
        on_done=_on_done
    )

    # Attach context to worker parent reference for patcher
    worker.parent = context

    # Start worker and handle Ctrl+C cleanly
    worker.start()
    try:
        while worker.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n\n[USER ABORT] Stopping separation...")
        worker.stop()
        worker.join(timeout=10)
        print("[USER ABORT] Separation aborted by user.")
        return 1

    worker.join()

    if done_result["success"]:
        print(f"\n[SUCCESS] Separation completed successfully!")
        if done_result["files"]:
            print(f"Generated {len(done_result['files'])} stem files:")
            for f in done_result["files"]:
                print(f"  - {f}")
        return 0
    else:
        print(f"\n[ERROR] Separation failed: {done_result['message']}")
        return 1
