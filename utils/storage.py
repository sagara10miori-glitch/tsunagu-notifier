import json
import os
import shutil
from datetime import datetime

DATA_DIR = "data"
BACKUP_DIR = os.path.join(DATA_DIR, "backup")

# ディレクトリが存在しない場合は作成
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


def load_json(path, default=None):
    """
    JSON を安全に読み込む。
    壊れている場合は default を返す。
    """
    if default is None:
        default = {}

    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        print(f"[WARNING] JSON load failed → {path}")
        return default


def save_json(path, data):
    """
    JSON を安全に保存する。
    保存前にバックアップを作成し、アトミック書き込みで破損を防ぐ。
    """
    # バックアップ作成
    create_backup(path)

    # 一時ファイルに書き込んでから rename（アトミック書き込み）
    temp_path = path + ".tmp"

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(temp_path, path)
    except Exception as e:
        print(f"[ERROR] Failed to save JSON → {path}")
        print(e)


def create_backup(path):
    """
    JSON のバックアップを作成する。
    ファイルが存在しない場合は何もしない。
    """
    if not os.path.exists(path):
        return

    filename = os.path.basename(path)
    date = datetime.now().strftime("%Y%m%d")
    backup_path = os.path.join(BACKUP_DIR, f"{filename}_{date}.json")

    try:
        shutil.copy2(path, backup_path)
    except Exception as e:
        print(f"[WARNING] Backup failed → {backup_path}")
        print(e)


def append_json_list(path, item):
    """
    JSON のリストに item を追加する。
    """
    data = load_json(path, default=[])
    data.append(item)
    save_json(path, data)


def clear_json(path):
    """
    JSON を空のリストとして初期化する。
    """
    save_json(path, [])
