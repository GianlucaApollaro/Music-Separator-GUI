import os
import wx
import requests

def get_writable_dir():
    """Returns a writable directory for logs or configs."""
    return os.getcwd()

def format_time(seconds):
    """Formats seconds into MM:SS."""
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{int(s):02d}"

def download_file(url, dest_path, progress_callback=None, overwrite=False):
    """Downloads a file from url to dest_path with optional progress callback."""
    if os.path.exists(dest_path) and not overwrite:
        return True
        
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(dest_path, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for data in response.iter_content(chunk_size=8192):
                    downloaded += len(data)
                    f.write(data)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        return True
    except Exception as e:
        print(f"Download error: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path) # Clean up partial file
        return False
