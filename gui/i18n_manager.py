import json
import os
import sys
import locale

class TranslationManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranslationManager, cls).__new__(cls)
            cls._instance.translations = {}
            cls._instance.current_lang = "en"
            cls._instance.load_language()
        return cls._instance

    def load_language(self, lang_code=None):
        """Loads the language file. If lang_code is None, tries to detect system language."""
        if lang_code is None:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang and sys_lang.startswith('it'):
                lang_code = 'it'
            elif sys_lang and sys_lang.startswith('es'):
                lang_code = 'es'
            else:
                lang_code = 'en'
        
        self.current_lang = lang_code
        
        # Look in i18n folder specifically
        # Assumes i18n folder is at the project root, two levels up from gui package or one level up from main
        # Adjust path finding logic as needed.
        if getattr(sys, 'frozen', False):
            # If frozen (packaged), resources are in sys._MEIPASS
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        i18n_path = os.path.join(base_path, 'i18n')
        file_path = os.path.join(i18n_path, f"{lang_code}.json")

        if not os.path.exists(file_path):
            # Fallback to English if file not found
            file_path = os.path.join(i18n_path, "en.json")
            if not os.path.exists(file_path):
                 print(f"Warning: Translation file not found at {file_path}")
                 self.translations = {}
                 return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
        except Exception as e:
            print(f"Error loading translation file: {e}")
            self.translations = {}

    def tr(self, key: str, **kwargs) -> str:
        """Returns the translation for the key, formatted with kwargs if provided, handling plurals if 'count' is present."""
        text = self.translations.get(key, key)
        if kwargs:
            if 'count' in kwargs:
                count = kwargs['count']
                plural_key = f"{key}_plural"
                if plural_key in self.translations:
                    text = self.translations[plural_key] if count != 1 else text
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text

# Global instance
i18n = TranslationManager()
