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
                "vocals": None  # Discard empty vocals extracted from instrumental
            }
        },
        "preset_chorus_hq": {
            "type": "chain",
            "model_1": "mel_band_roformer_kim_ft_unwa.ckpt",
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
            "model_1": "mel_band_roformer_becruily_deux.ckpt",
            "model_2": "BS-Roformer-SW.ckpt",
            "model_3": "MDX23C-DrumSep-aufr33-jarredou.ckpt",
            "pass_stem": "instrumental",
            "pass_stem_2": "drums",
            "m1_keep_name": "_Vocals",
            "m2_keep_pass_stem_name": "_Drums_Stereo", # Keep the stereo drums too
            "m2_rename_map": {
                "bass": "_Bass",
                "piano": "_Piano",
                "guitar": "_Guitar",
                "other": "_Other",
                "drums": "_Drums_Stereo",
                "vocals": None  # Discard empty vocals extracted from instrumental
            },
            "m3_rename_map": {
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
    }

    @classmethod
    def get_preset_config(cls, preset_key: str) -> dict:
        return cls.presets_config.get(preset_key, {})

    @classmethod
    def get_preset_name(cls, preset_key: str, i18n_instance) -> str:
        return i18n_instance.tr(preset_key)
