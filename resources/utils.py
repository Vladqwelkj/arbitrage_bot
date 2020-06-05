import threading


def in_new_thread(my_func):
    def wrapper(*args, **kwargs):
        my_thread = threading.Thread(target=my_func, args=args, kwargs=kwargs, daemon=True)
        my_thread.start()
    return wrapper