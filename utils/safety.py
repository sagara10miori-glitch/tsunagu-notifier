import os
import time
from datetime import datetime

LOCK_FILE = "run.lock"
TIMEOUT_SECONDS = 60  # 60秒以上かかったら警告


def create_lock():
    """
    二重実行防止のためのロックファイルを作成する。
    既に存在する場合は True を返す（実行中と判断）。
    """
    if os.path.exists(LOCK_FILE):
        print("[INFO] Another run is active. Skipping.")
        return True

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    return False


def remove_lock():
    """
    ロックファイルを削除する。
    """
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


def start_timer():
    """
    実行開始時間を返す。
    """
    return time.time()


def check_timeout(start_time):
    """
    実行時間が TIMEOUT_SECONDS を超えた場合に警告を出す。
    """
    elapsed = time.time() - start_time
    if elapsed > TIMEOUT_SECONDS:
        print(f"[WARNING] Execution time exceeded {TIMEOUT_SECONDS} seconds ({elapsed:.1f}s)")


def safe_run(main_func):
    """
    notify.py のメイン処理を安全に実行するためのラッパー。
    - ロックファイル作成
    - タイマー開始
    - main_func 実行
    - タイムアウト監視
    - ロック削除
    """
    if create_lock():
        return  # 二重実行なので終了

    start_time = start_timer()

    try:
        main_func()
    except Exception as e:
        print("[ERROR] notify.py crashed")
        print(e)
    finally:
        check_timeout(start_time)
        remove_lock()
