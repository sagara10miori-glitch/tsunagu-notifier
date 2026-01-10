import traceback

def safe_run(func):
    try:
        func()
    except Exception as e:
        print("[ERROR] Exception occurred:")
        print(e)
        traceback.print_exc()
