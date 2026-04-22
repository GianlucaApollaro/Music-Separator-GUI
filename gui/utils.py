import os
import logging
import requests
from typing import Optional, Callable, Tuple

logger = logging.getLogger(__name__)

def get_writable_dir() -> str:
    """Returns a writable directory for logs or configs."""
    return os.getcwd()

def format_time(seconds: float) -> str:
    """Formats seconds into MM:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def download_file(url,
                  dest_path,
                  progress_callback: Optional[Callable[[int, int], None]] = None,
                  overwrite: bool = False,
                  timeout: Tuple[int, int] = (10, 30)) -> bool:
    """
    Scarica un file con timeout e callback di progresso.
    Restituisce True se successo, False altrimenti.
    """
    # Coerce types defensively — valori non-stringa (es. interi dal JSON) vengono
    # intercettati qui prima di causare errori nelle chiamate os.path.*
    if not isinstance(url, str):
        logger.warning(f"Skipped download: URL non valido (tipo {type(url).__name__}): '{url}'")
        return False
    if not isinstance(dest_path, str):
        logger.warning(f"Skipped download: dest_path non valido (tipo {type(dest_path).__name__}): '{dest_path}'")
        return False

    if not url.startswith("http"):
        logger.warning(f"Skipped download: URL senza schema '{url}' per '{os.path.basename(dest_path)}'")
        return False

    if os.path.exists(dest_path) and not overwrite:
        return True

    try:
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        with open(dest_path, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    f.write(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Timeout durante download {url}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Errore di connessione per {url}")
    except Exception as e:
        logger.error(f"Download fallito: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
    return False
