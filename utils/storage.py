import tempfile
import os
import json

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def append_json_list(path, item):
    data = load_json(path, [])
    if not isinstance(data, list):
        data = []
    data.append(item)
    save_json(path, data)

def clear_json(path):
    save_json(path, [])
