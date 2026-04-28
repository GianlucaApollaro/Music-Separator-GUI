import os
import json
import logging

logger = logging.getLogger(__name__)

from gui.utils import get_app_data_dir

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.data_dir = get_app_data_dir()
        self.config_file = os.path.join(self.data_dir, config_file)
        self.config = {
            "output_dir": os.path.join(self.data_dir, 'output'),
            "model_1": "BS-Roformer-SW.ckpt",
            "model_2": "UVR-MDX-NET-Inst_HQ_5.onnx",
            "preset": 0,
            "enable_ensemble": False,
            "language": None
        }
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

# Global instance
config = ConfigManager()
