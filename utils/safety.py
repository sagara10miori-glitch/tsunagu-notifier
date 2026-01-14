def safe_run(func):
    try:
        func()
    except Exception:
        # 必要ならログを追加可能
        pass
