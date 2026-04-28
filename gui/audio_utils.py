import os
import re
import numpy as np
import soundfile as sf
from typing import Tuple

def stem_from_filename(filename: str) -> str:
    """Estrae il nome dello stem dal filename generato da audio_separator."""
    basename = os.path.basename(filename)
    base = os.path.splitext(basename)[0]
    
    # Cerca pattern _(qualcosa) tipici dei roformer o demucs
    matches = re.findall(r"_\(([^)]+)\)", base)
    if matches:
        stem = matches[-1].lower()
    else:
        parts = base.split("_")
        stem = parts[-1].lower().strip("()") if parts else base.lower()
        
    # Sinonimi per compatibilità (rimosso per permettere distinzione tra Other e Instrumental)
    # if stem == "other":
    #     stem = "instrumental"
        
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
