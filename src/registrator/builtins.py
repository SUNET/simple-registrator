import os
import etcd
from backends import backend, monitor
from time import sleep


@backend(name="etcd")
class Etcd(object):

    def __init__(self):
        self.client = etcd.Client(host=os.environ.get('ETCD_HOST','127.0.0.1'),
                                  port=int(os.environ.get('ETCD_PORT', '4001')))

    def start(self, info):
        self.client.set()


@backend(name="log")
class Log(object):

    def __call__(self, *args, **kwargs):
        print args[0]


@backend(name="monitor_test")
class TestMonitor(object):

    def __init__(self):
        self.threads = dict()
        self.done = False

    def _mon(self, info):
        self.done = False
        while not self.done:
            sleep(10)
            print info

    def start(self, info):
        if 'container' in info:
            t = monitor(self._mon, info)
            self.threads[info['container']] = t

    def stop(self, info):
        if 'container' in info and info['container'] in self.threads:
            t = self.threads[info['container']]
            self.done = True
            t.join()