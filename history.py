import json

def load_history(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if json.JSONDecodeError:
            print("Warning: Saved conversation file is corrupted. Starting fresh.")
        return None

def save_history(file_path, messages):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=4)
