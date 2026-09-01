import os
import re
import logging
import numpy as np
import soundfile as sf
from typing import Tuple, List, Optional, Dict

logger = logging.getLogger(__name__)

_CATALOG_STEMS_MAP: Optional[Dict[str, List[str]]] = None

def _get_catalog_stems_map() -> Dict[str, List[str]]:
    global _CATALOG_STEMS_MAP
    if _CATALOG_STEMS_MAP is not None:
        return _CATALOG_STEMS_MAP
        
    _CATALOG_STEMS_MAP = {}
    try:
        from audio_separator.separator import Separator
        sep = Separator()
        catalog = sep.list_supported_model_files()
        
        def build_map(obj):
            if isinstance(obj, dict):
                if 'filename' in obj and 'stems' in obj:
                    fn = str(obj['filename']).lower().strip()
                    stems = obj['stems']
                    if fn and isinstance(stems, list) and len(stems) > 0:
                        _CATALOG_STEMS_MAP[fn] = stems
                for v in obj.values():
                    build_map(v)
            elif isinstance(obj, list):
                for item in obj:
                    build_map(item)
                    
        build_map(catalog)
    except Exception as e:
        logger.warning(f"Could not load audio-separator catalog stems: {e}")
        
    return _CATALOG_STEMS_MAP

def get_model_stems(model_name: str) -> List[str]:
    """Retrieves the exact list of output stems for a model, using audio-separator catalog or intelligent fallbacks."""
    if not model_name:
        return ["vocals", "instrumental"]
        
    model_lower = model_name.lower().strip()
    
    # 1. Check audio_separator catalog first
    cat_map = _get_catalog_stems_map()
    if model_lower in cat_map:
        return list(cat_map[model_lower])
        
    # 2. Rule-based fallbacks for unlisted/custom models
    if "53_stems" in model_lower or "53stems" in model_lower or "53 stems" in model_lower or "mvsep_mega" in model_lower:
        return [
            'accordion', 'acoustic-guitar', 'back-vocal', 'banjo', 'bass', 'bassoon',
            'bells', 'bowed_strings', 'brass', 'cello', 'clarinet', 'congas',
            'digital-piano', 'dobro', 'double-bass', 'drums', 'electric-guitar',
            'flute', 'french-horn', 'glockenspiel', 'guitar', 'harmonica', 'harp',
            'harpsichord', 'hh', 'keys', 'kick', 'lead-vocal', 'mandolin', 'marimba',
            'oboe', 'organ', 'percussion', 'piano', 'saxophone', 'sitar', 'snare',
            'strings', 'synth', 'tambourine', 'timpani', 'toms', 'triangle',
            'trombone', 'trumpet', 'tuba', 'ukulele', 'viola', 'violin', 'vocal',
            'wind', 'wind-chimes', 'woodwind'
        ]

    if "drumsep" in model_lower or "drum_sep" in model_lower or "drum-sep" in model_lower:
        return ["kick", "snare", "toms", "hh", "ride", "crash", "other"]
        
    if "dereverb" in model_lower or "de-reverb" in model_lower or "deecho" in model_lower or "de-echo" in model_lower:
        if "echo" in model_lower:
            return ["dry", "no dry"]
        return ["noreverb", "reverb"]
        
    if "denoise" in model_lower:
        return ["dry", "other"]
        
    if "bowedstrings" in model_lower or "bowed_strings" in model_lower or "bowed strings" in model_lower or "gilliaan_bowedstrings" in model_lower:
        return ["strings", "other"]

    if "duet" in model_lower or "7.9319" in model_lower or "duet_dual" in model_lower:
        return ["singer_1", "singer_2"]

    if "synth_lead" in model_lower or "synth lead" in model_lower or "lead_synth" in model_lower or "lead synth" in model_lower or "4.9869" in model_lower or "synth" in model_lower:
        return ["synth lead", "synth accompaniment"]

    if "guitar" in model_lower:
        return ["guitar", "instrumental"]
        
    if "crowd" in model_lower or "applause" in model_lower:
        return ["crowd", "instrumental"]
        
    if "aspiration" in model_lower or "breath" in model_lower:
        return ["aspiration", "other"]
        
    if "male_female" in model_lower or "gender" in model_lower or "chorus" in model_lower:
        return ["male", "female"]
        
    if "htdemucs_6s" in model_lower or "roformer-sw" in model_lower:
        return ["vocals", "drums", "bass", "piano", "guitar", "other"]
        
    return ["vocals", "instrumental"]

SYNONYM_GROUPS = [
    {"dry", "denoise", "dereverb", "noreverb", "no_reverb", "clean", "no_noise", "nonoise", "lead", "vocals"},
    {"other", "instrumental", "noise", "reverb", "no_dry", "nodry", "bleed", "extra"},
    {"hh", "hi-hat", "hihat"},
    {"crash", "ride", "cymbals"},
    {"male", "vocals"},
    {"female", "other"}
]

def stems_are_equivalent(stem1: str, stem2: str) -> bool:
    """Checks if two stem names are strictly identical or semantically equivalent."""
    s1 = stem1.lower().strip("() ")
    s2 = stem2.lower().strip("() ")
    if s1 == s2:
        return True
        
    for group in SYNONYM_GROUPS:
        if s1 in group and s2 in group:
            return True
            
    return False

def get_rename_suffix(stem: str, rename_map: Dict[str, Optional[str]]) -> Tuple[bool, Optional[str]]:
    """
    Looks up a stem in a rename map (by exact name or synonym).
    Returns (found_in_map, suffix).
    suffix can be None (discard stem) or str (custom suffix e.g. '_Instrumental').
    """
    if not rename_map:
        return False, f"_{stem.capitalize()}"
        
    stem_lower = stem.lower().strip("() ")
    
    # Direct match
    if stem_lower in rename_map:
        return True, rename_map[stem_lower]
        
    # Synonym match
    for k, v in rename_map.items():
        if stems_are_equivalent(stem_lower, k):
            return True, v
            
    return False, f"_{stem.capitalize()}"

def stem_from_filename(filename: str) -> str:
    """Estrae il nome dello stem dal filename generato da audio_separator."""
    basename = os.path.basename(filename)
    base = os.path.splitext(basename)[0]
    
    matches = re.findall(r"_\(([^)]+)\)", base)
    if matches:
        stem = matches[-1].lower().strip("()")
    else:
        parts = base.split("_")
        stem = parts[-1].lower().strip("()") if parts else base.lower()
        
    return stem

def blend_audio(audio1: np.ndarray, audio2: np.ndarray, algorithm: str = "avg_wave") -> np.ndarray:
    """Combina due array audio usando min_wave, max_wave, median_wave o avg_wave."""
    min_len = min(len(audio1), len(audio2))
    a = audio1[:min_len]
    b = audio2[:min_len]
    
    if algorithm == "min_wave":
        return np.minimum(a, b)
    elif algorithm == "max_wave":
        return np.maximum(a, b)
    elif algorithm == "median_wave":
        return np.median(np.stack([a, b]), axis=0)
    else:  # avg_wave (default)
        return (a + b) / 2.0

def read_audio_pair(path1: str, path2: str) -> Tuple[np.ndarray, int, np.ndarray]:
    """Legge due file audio, restituisce (data1, samplerate, data2)."""
    data1, sr1 = sf.read(path1)
    data2, sr2 = sf.read(path2)
    if sr1 != sr2:
        raise ValueError(f"Samplerate mismatch: {sr1} vs {sr2}")
    return data1, sr1, data2

def get_audio_volume_stats(fpath: str) -> Tuple[float, float]:
    """
    Calcola il picco massimo (dBFS) e l'energia media RMS (dBFS) di un file audio.
    Utilizza soundfile con lettura a blocchi di 64k frame (zero sovraccarico RAM).
    Se soundfile fallisce per codec non supportati nativamente, ripiega su FFmpeg volumedetect.
    Restituisce (peak_db, rms_db).
    """
    if not os.path.exists(fpath):
        return -120.0, -120.0

    try:
        with sf.SoundFile(fpath) as audio:
            peak_val = 0.0
            sum_sq = 0.0
            total_samples = 0
            block_size = 65536
            while True:
                data = audio.read(block_size, dtype='float32', always_2d=True)
                if len(data) == 0:
                    break
                block_peak = float(np.max(np.abs(data)))
                if block_peak > peak_val:
                    peak_val = block_peak
                sum_sq += float(np.sum(data ** 2))
                total_samples += data.size

            peak_db = 20.0 * np.log10(peak_val) if peak_val > 1e-6 else -120.0
            rms = np.sqrt(sum_sq / total_samples) if total_samples > 0 else 0.0
            rms_db = 20.0 * np.log10(rms) if rms > 1e-6 else -120.0
            return float(peak_db), float(rms_db)
    except Exception as e:
        logger.debug(f"soundfile failed for {fpath}, trying ffmpeg: {e}")
        try:
            import subprocess
            vol_res = subprocess.run(
                ['ffmpeg', '-y', '-i', fpath, '-af', 'volumedetect', '-f', 'null',
                 os.devnull if os.name != 'nt' else 'NUL'],
                capture_output=True, text=True, errors='replace'
            )
            peak_m = re.search(r'max_volume:\s*([-\d.]+)\s*dB', vol_res.stderr)
            mean_m = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', vol_res.stderr)
            peak_db = float(peak_m.group(1)) if peak_m else -120.0
            rms_db = float(mean_m.group(1)) if mean_m else -120.0
            return peak_db, rms_db
        except Exception:
            return -120.0, -120.0

