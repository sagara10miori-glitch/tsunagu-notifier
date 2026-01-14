import json
import os
from typing import Any

def load_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def append_json_list(path: str, item: Any):
    data = load_json(path, default=[])
    if not isinstance(data, list):
        data = []
    data.append(item)
    save_json(path, data)

def clear_json(path: str):
    if os.path.exists(path):
        save_json(path, [])
