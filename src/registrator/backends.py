from threading import Thread

import os
import logging

logger = logging.getLogger(__name__)

registry = dict()


def backend(*args, **kwargs):

    def deco_backend(f):
        enabled = kwargs.get('enabled', True)

        # Allow overriding enabled status of backends through environment variables
        # Set REGISTRATOR_ETCD to true, 1 or enabled to enable backend 'etcd'
        # Set REGISTRATOR_ETCD to false, 0 or disabled to disable backend 'etcd'
        if 'name' in kwargs:
            env_name = 'REGISTRATOR_{!s}'.format(kwargs['name'].upper())
            _value = os.environ.get(env_name, str(enabled))
            if _value.lower() in ['true', 'enabled', '1']:
                enabled = True
            elif _value.lower() in ['false', 'disabled', '0']:
                enabled = False
        if enabled:
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

