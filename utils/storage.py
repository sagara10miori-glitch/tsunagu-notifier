import json
import os

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def append_json_list(path, item):
    data = load_json(path, default=[])
    data.append(item)
    save_json(path, data)

def clear_json(path):
    save_json(path, [])
