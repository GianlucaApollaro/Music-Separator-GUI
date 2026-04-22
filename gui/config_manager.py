import os
import json

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = os.path.join(os.getcwd(), config_file)
        self.config = {
            "output_dir": os.path.join(os.getcwd(), 'output'),
            "model_1": "BS-Roformer-SW.ckpt",
            "model_2": "UVR-MDX-NET-Inst_HQ_5.onnx",
            "preset": 0,
            "enable_ensemble": False
        }
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

# Global instance
config = ConfigManager()
