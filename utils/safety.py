def safe_run(func):
    try:
        func()
    except Exception:
        # ログを出したければここに print や logging を追加
        pass
