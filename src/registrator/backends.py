from threading import Thread

registry = dict()


def backend(*args, **kwargs):

    def deco_none(f):
        return f

    def deco_backend(f):
        f_name = kwargs.get('name', f.__name__)
        registry[f_name] = f
        return f

    if 1 == len(args):
        f = args[0]
        registry[f.__name__] = f
        return deco_none
    else:
        return deco_backend


def backends():
    return registry.values()


def monitor(task, *args, **kwargs):
    t = Thread(target=task, args=args, kwargs=kwargs)
    t.start()
    return t

