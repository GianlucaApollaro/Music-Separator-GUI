import os
import sys
import json
import logging

logger = logging.getLogger(__name__)

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
            "model_1": "gilliaan_bowedstrings_bs_v1.ckpt",
            "model_2": "bs_roformer_karaoke_frazer_becruily.ckpt",
            "model_3": "mel_band_roformer_becruily_deux.ckpt",
            "model_4": "BS-Roformer-SW.ckpt",
            "model_5": "MDX23C-DrumSep-aufr33-jarredou.ckpt",
            "pass_stem": "other",
            "pass_stem_2": "instrumental",
            "pass_stem_3": "instrumental",
            "pass_stem_4": "drums",
            "m1_gain_db": -3.0,
            "m1_rename_map": {
                "strings": "_Strings"
            },
            "m2_keep_name": "_Lead",
            "m3_keep_pass_stem_name": "_Instrumental_No_Strings",
            "m3_rename_map": {
                "vocals": "_Backing"
            },
            "m4_keep_pass_stem_name": "_Drums_Stereo", # Keep the stereo drums too
            "m4_rename_map": {
                "bass": "_Bass",
                "piano": "_Piano",
                "guitar": "_Guitar",
                "other": "_Other",
                "drums": "_Drums_Stereo",
                "vocals": "_Extra"
            },
            "m5_rename_map": {
                "kick": "_Kick",
                "snare": "_Snare",
                "hi-hat": "_Hi-Hat",
                "cymbals": "_Cymbals",
                "tom-toms": "_Toms",
                "other": "_Drums_Other"
            },
            "post_mix": [
                {
                    "stems": ["_Strings", "_Instrumental_No_Strings"],
                    "output": "_Instrumental",
                    "delete_sources": ["_Instrumental_No_Strings"]
                }
            ]
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
            
            if not isinstance(custom_presets, dict):
                logger.warning("Custom presets file is not a JSON object, ignoring it.")
                return

            for key, config in custom_presets.items():
                # A non-dict entry would crash later on config.get(...)
                if not isinstance(config, dict):
                    logger.warning(f"Skipping malformed custom preset '{key}'.")
                    continue

                if not key.startswith("custom_"):
                    key = f"custom_{key}"

                cls.presets_config[key] = config
                if key not in cls.preset_keys:
                    cls.preset_keys.append(key)
        except Exception as e:
            logger.error(f"Error loading custom presets: {e}")

    @staticmethod
    def _write_json_atomic(path: str, payload: dict):
        """Write JSON via temp file + os.replace so a crash cannot truncate the target."""
        tmp_path = f"{path}.tmp"
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise

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
            cls._write_json_atomic(path, custom_presets)
        except Exception as e:
            # Do not report success for a preset that never reached the disk.
            logger.error(f"Error saving custom preset: {e}")
            return None

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
                cls._write_json_atomic(path, custom_presets)

            if preset_key in cls.presets_config:
                del cls.presets_config[preset_key]
            if preset_key in cls.preset_keys:
                cls.preset_keys.remove(preset_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting custom preset: {e}")
            return False

    @classmethod
    def export_presets(cls, export_path: str, keys: list = None) -> tuple:
        """
        Exports custom presets (or specific keys) to a portable JSON file.
        Returns (count_exported, error_message).
        """
        try:
            cls.load_custom_presets()
            target_keys = keys if keys is not None else [k for k in cls.preset_keys if k.startswith("custom_")]
            if not target_keys:
                return (0, "No presets to export")

            export_data = {
                "format_version": "1.0",
                "presets": {}
            }
            for k in target_keys:
                cfg = cls.presets_config.get(k)
                if cfg:
                    p_name = cfg.get("name", k)
                    export_data["presets"][p_name] = cfg

            cls._write_json_atomic(export_path, export_data)
            return (len(export_data["presets"]), "")
        except Exception as e:
            logger.error(f"Error exporting presets: {e}")
            return (0, str(e))

    @classmethod
    def import_presets(cls, import_path: str, overwrite: bool = True) -> tuple:
        """
        Imports presets from a JSON file.
        Accepts:
          - {"format_version": "...", "presets": {"Name": {config}, ...}}
          - {"custom_key": {config}, ...}
          - {"Name": {config}, ...}
        Returns (count_imported, list_of_names, error_message).
        """
        if not os.path.exists(import_path):
            return (0, [], "File not found")

        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return (0, [], "Invalid JSON format: expected an object")

            presets_to_import = data.get("presets", data)
            if not isinstance(presets_to_import, dict):
                return (0, [], "Invalid presets payload")

            imported_names = []
            cls.load_custom_presets()

            for key_or_name, cfg in presets_to_import.items():
                if not isinstance(cfg, dict):
                    continue

                if key_or_name in ("format_version", "presets"):
                    continue

                # Must have basic structure (type, model_1 or model_name)
                if "model_1" not in cfg and "model_name" not in cfg and "type" not in cfg:
                    continue

                p_name = cfg.get("name", key_or_name.replace("custom_", "").replace("_", " ").title())
                saved_key = cls.save_custom_preset(p_name, cfg)
                if saved_key:
                    imported_names.append(p_name)

            cls.load_custom_presets()
            return (len(imported_names), imported_names, "")
        except Exception as e:
            logger.error(f"Error importing presets: {e}")
            return (0, [], str(e))
