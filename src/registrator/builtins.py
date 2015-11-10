import os
import etcd
from backends import backend


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