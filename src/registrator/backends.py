from threading import Thread

registry = dict()


def backend(*args, **kwargs):

    def deco_backend(f):
        if kwargs.get('enabled', True):
            f_name = kwargs.get('name', f.__name__)
            registry[f_name] = f()
        return f

    return deco_backend


def get_backends():
    return registry.values()


def monitor(task, *args, **kwargs):
    t = Thread(target=task, args=args, kwargs=kwargs)
    t.start()
    return t

