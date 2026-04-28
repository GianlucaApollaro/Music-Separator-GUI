import json
import os
import sys
import locale

from gui.utils import get_base_path

class TranslationManager:
    _instance = None
    SUPPORTED_LANGS = {"it", "es", "en"}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranslationManager, cls).__new__(cls)
            cls._instance.translations = {}
            cls._instance.current_lang = "en"
            cls._instance.load_language()
        return cls._instance

    def _normalize_lang(self, value):
        if not value:
            return None
        value = str(value).strip().lower()
        
        # Handle full language names (common on Windows, e.g. "Italian_Italy")
        if value.startswith(('it', 'ital')): return 'it'
        if value.startswith(('es', 'span')): return 'es'
        if value.startswith(('en', 'engl')): return 'en'
        
        value = value.replace('-', '_')
        lang = value.split('_')[0].split('.')[0]
        return lang if lang in self.SUPPORTED_LANGS else None

    def _get_macos_lang(self):
        if sys.platform != "darwin":
            return None
        try:
            # Requires pyobjc-framework-Cocoa
            from Foundation import NSLocale
            langs = NSLocale.preferredLanguages()
            if langs:
                for lang in langs:
                    normalized = self._normalize_lang(lang)
                    if normalized:
                        return normalized
        except Exception:
            pass
        return None

    def _get_system_lang(self):
        # 1. Try macOS native API
        mac_lang = self._get_macos_lang()
        if mac_lang:
            return mac_lang

        # 2. Try environment variables
        for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            val = os.environ.get(var)
            normalized = self._normalize_lang(val)
            if normalized:
                return normalized

        # 3. Try standard locale module
        try:
            import locale
            # getdefaultlocale is deprecated but more reliable on Windows for system defaults
            sys_lang, _ = locale.getdefaultlocale()
            normalized = self._normalize_lang(sys_lang)
            if normalized:
                return normalized
            
            # Fallback to getlocale
            sys_lang, _ = locale.getlocale()
            normalized = self._normalize_lang(sys_lang)
            if normalized:
                return normalized
        except Exception:
            pass

        return "en"

    def load_language(self, lang_code=None):
        if lang_code is None:
            # Check config first
            from gui.config_manager import config
            lang_code = config.get("language")
            
            # If not in config, use system language
            if lang_code is None:
                lang_code = self._get_system_lang()

        if lang_code not in self.SUPPORTED_LANGS:
            lang_code = "en"

        self.current_lang = lang_code

        base_path = get_base_path()
        i18n_path = os.path.join(base_path, "i18n")
        file_path = os.path.join(i18n_path, f"{lang_code}.json")

        if not os.path.exists(file_path):
            self.current_lang = "en"
            file_path = os.path.join(i18n_path, "en.json")
            if not os.path.exists(file_path):
                self.translations = {}
                return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except Exception:
            self.translations = {}

    def tr(self, key: str, **kwargs) -> str:
        """Returns the translation for the key, formatted with kwargs if provided."""
        text = self.translations.get(key, key)
        if kwargs:
            if "count" in kwargs:
                count = kwargs["count"]
                plural_key = f"{key}_plural"
                if plural_key in self.translations:
                    text = self.translations[plural_key] if count != 1 else text
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text

# Global instance
i18n = TranslationManager()
