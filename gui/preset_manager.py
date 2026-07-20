import os
import sys
import json

class PresetManager:
    preset_keys = [
        "preset_none", 
        "preset_vocal_split", 
        "preset_vocal_dereverb",
        "preset_ultimate_stems",
        "preset_ultimate_drums",
        "preset_chorus_hq",
        "preset_guitar_specialist",
        "preset_crowd_live",
        "preset_vocal_rvc",
        "preset_only_drums",
        "preset_drums_no_drums",
    ]

    presets_config = {
        "preset_none": {},
        "preset_vocal_split": {
            "type": "chain",
            "model_1": "bs_roformer_karaoke_frazer_becruily.ckpt",
            "model_2": "mel_band_roformer_becruily_deux.ckpt",
            "pass_stem": "instrumental",
            "m1_keep_name": "_Lead",
            "m2_rename_map": {
                "vocals": "_Backing",
                "instrumental": "_Instrumental",
                "other": "_Instrumental"
            }
        },
        "preset_vocal_dereverb": {
            "type": "chain",
            "model_1": "mel_band_roformer_becruily_deux.ckpt",
            "model_2": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
            "pass_stem": "vocals",
            "m1_keep_name": "_Instrumental",
            "m2_rename_map": {
                "noreverb": "_DeReverb",
                "reverb": "_Reverb"
            }
        },
        "preset_ultimate_stems": {
            "type": "chain",
            "model_1": "mel_band_roformer_becruily_deux.ckpt",
            "model_2": "BS-Roformer-SW.ckpt",
            "pass_stem": "instrumental",
            "m1_keep_name": "_Vocals",
            "m1_keep_pass_stem_name": "_Instrumental",
            "m2_rename_map": {
                "drums": "_Drums",
                "bass": "_Bass",
                "piano": "_Piano",
                "guitar": "_Guitar",
                "other": "_Other",
                "vocals": "_Extra"
            }
        },
        "preset_chorus_hq": {
            "type": "chain",
            "model_1": "mel_band_roformer_becruily_deux.ckpt",
            "model_2": "bs_roformer_male_female_by_aufr33_sdr_7.2889.ckpt",
            "pass_stem": "vocals",
            "m1_keep_name": "_Instrumental",
            "m2_rename_map": {
                "vocals": "_Female",
                "other": "_Male",
                "instrumental": "_Male",
                "male": "_Male",
                "female": "_Female"
            }
        },
        "preset_ultimate_drums": {
            "type": "chain",
            "model_1": "bs_roformer_karaoke_frazer_becruily.ckpt",
            "model_2": "mel_band_roformer_becruily_deux.ckpt",
            "model_3": "BS-Roformer-SW.ckpt",
            "model_4": "MDX23C-DrumSep-aufr33-jarredou.ckpt",
            "pass_stem": "instrumental",
            "pass_stem_2": "instrumental",
            "pass_stem_3": "drums",
            "m1_keep_name": "_Lead",
            "m2_rename_map": {
                "vocals": "_Backing"
            },
            "m3_keep_pass_stem_name": "_Drums_Stereo", # Keep the stereo drums too
            "m3_rename_map": {
                "bass": "_Bass",
                "piano": "_Piano",
                "guitar": "_Guitar",
                "other": "_Other",
                "drums": "_Drums_Stereo",
                "vocals": "_Extra"
            },
            "m4_rename_map": {
                "kick": "_Kick",
                "snare": "_Snare",
                "hi-hat": "_Hi-Hat",
                "cymbals": "_Cymbals",
                "tom-toms": "_Toms",
                "other": "_Drums_Other"
            }
        },
        "preset_guitar_specialist": {
            "name": "Guitar Extraction (3 Stems)",
            "type": "chain",
            "model_1": "mel_band_roformer_becruily_deux.ckpt",
            "model_2": "mel_band_roformer_guitar_becruily.ckpt",
            "pass_stem": "instrumental",
            "m1_keep_name": "_Vocals",
            "m2_rename_map": {
                "guitar": "_Guitar",
                "other": "_Other",
                "no guitar": "_Other"
            }
        },
        "preset_crowd_live": {
            "type": "chain",
            "model_1": "mel_band_roformer_crowd_aufr33_viperx_sdr_8.7144.ckpt",
            "model_2": "mel_band_roformer_becruily_deux.ckpt",
            "pass_stem": "other",
            "m1_keep_name": "_Crowd",
            "m2_rename_map": {
                "vocals": "_Lead",
                "instrumental": "_Instrumental",
                "other": "_Instrumental"
            }
        },
        "preset_vocal_rvc": {
            "type": "chain",
            "model_1": "mel_band_roformer_karaoke_becruily.ckpt",
            "model_2": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
            "pass_stem": "vocals",
            "m1_keep_name": "_Instrumental_BVs",
            "m2_rename_map": {
                "noreverb": "_Lead_Clean",
                "reverb": "_Lead_Reverb"
            }
        },
        "preset_only_drums": {
            "type": "single",
            "model_1": "BS-Roformer-SW.ckpt",
            "rename_map": {
                "drums": "_Drums"
            }
        },
        "preset_drums_no_drums": {
            "type": "single",
            "model_1": "BS-Roformer-SW.ckpt",
            "rename_map": {
                "drums": "_Drums"
            },
            "mix_remaining_to": "_No_Drums"
        },
    }

    @classmethod
    def get_preset_config(cls, preset_key: str) -> dict:
        return cls.presets_config.get(preset_key, {})

    @classmethod
    def get_preset_name(cls, preset_key: str, i18n_instance) -> str:
        if preset_key.startswith("custom_"):
            return cls.presets_config.get(preset_key, {}).get("name", preset_key)
        return i18n_instance.tr(preset_key)

    @classmethod
    def _get_custom_presets_path(cls) -> str:
        if getattr(sys, 'frozen', False):
            if sys.platform == 'darwin':
                # On macOS app bundle, sys.executable is inside the .app bundle
                # We save outside the .app for portability.
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(sys.executable))))
            else:
                app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(app_dir, 'custom_presets.json')

    @classmethod
    def load_custom_presets(cls):
        """Loads custom presets from the portable JSON file and merges them."""
        # Ensure we don't duplicate keys if called multiple times
        cls.preset_keys = [k for k in cls.preset_keys if not k.startswith("custom_")]
        for k in list(cls.presets_config.keys()):
            if k.startswith("custom_"):
                del cls.presets_config[k]

        path = cls._get_custom_presets_path()
        if not os.path.exists(path):
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                custom_presets = json.load(f)
            
            for key, config in custom_presets.items():
                if not key.startswith("custom_"):
                    key = f"custom_{key}"
                
                cls.presets_config[key] = config
                if key not in cls.preset_keys:
                    cls.preset_keys.append(key)
        except Exception as e:
            print(f"Error loading custom presets: {e}")

    @classmethod
    def save_custom_preset(cls, name: str, config: dict) -> str:
        """Saves a custom preset to the JSON file and updates memory. Returns the key."""
        import re
        normalized_name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        preset_key = f"custom_{normalized_name}"
        
        base_key = preset_key
        counter = 1
        while preset_key in cls.presets_config:
            if cls.presets_config[preset_key].get("name") == name:
                break
            preset_key = f"{base_key}_{counter}"
            counter += 1

        config["name"] = name

        path = cls._get_custom_presets_path()
        custom_presets = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    custom_presets = json.load(f)
            except Exception:
                custom_presets = {}

        custom_presets[preset_key] = config

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(custom_presets, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving custom preset: {e}")

        cls.presets_config[preset_key] = config
        if preset_key not in cls.preset_keys:
            cls.preset_keys.append(preset_key)
            
        return preset_key

    @classmethod
    def delete_custom_preset(cls, preset_key: str) -> bool:
        """Deletes a custom preset from the JSON file and memory."""
        if not preset_key.startswith("custom_"):
            return False

        path = cls._get_custom_presets_path()
        if not os.path.exists(path):
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                custom_presets = json.load(f)
            
            if preset_key in custom_presets:
                del custom_presets[preset_key]
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(custom_presets, f, indent=4, ensure_ascii=False)
            
            if preset_key in cls.presets_config:
                del cls.presets_config[preset_key]
            if preset_key in cls.preset_keys:
                cls.preset_keys.remove(preset_key)
            return True
        except Exception as e:
            print(f"Error deleting custom preset: {e}")
            return False
