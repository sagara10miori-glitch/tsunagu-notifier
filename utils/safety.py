def safe_run(func):
    try:
        func()
    except Exception:
        pass
