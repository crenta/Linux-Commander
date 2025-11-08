import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent / "settings.json"

# Default settings in case the file doesn't exist yet
DEFAULT_SETTINGS = {
    "active_provider": "Mistral",
    "api_keys": {
        "Mistral": "",
        "OpenAI": "",
        "Gemini": "",
        "Claude": ""
    },
    "models": {
        "Mistral": "open-mistral-7b",
        "OpenAI": "gpt-3.5-turbo",
        "Gemini": "gemini-2.5-flash-lite",
        "Claude": "claude-3-haiku-20240307"
    }
}

def load_settings():
    """Loads settings from the JSON file, or returns defaults if missing."""
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            # Ensure all necessary keys exist (in case of partial updates)
            for key, value in DEFAULT_SETTINGS.items():
                 if key not in settings:
                     settings[key] = value
            return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS

def save_settings(settings_data):
    """Saves the provided settings dictionary to the JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False