import os
import etcd
from backends import backend, monitor
from time import sleep
import logging
import pprint
import socket

logger = logging.getLogger(__name__)


@backend(name='etcd', enabled=False)
class Etcd(object):

    def __init__(self):
        self.client = etcd.Client(host=os.environ.get('ETCD_HOST', '127.0.0.1'),
                                  port=int(os.environ.get('ETCD_PORT', '2379')))
        # IP address (and hostname) need to be supplied as environment variables if the
        # simple-registrator is running in a docker container in bridge networking mode
        self.hostname = os.environ.get('REGISTRATOR_HOSTNAME', socket.gethostname())
        self.ipv4 = os.environ.get('REGISTRATOR_HOSTIPV4', socket.gethostbyname(self.hostname))

    def start(self, info):
        image_name = info['Config']['Image']
        ns = os.environ.get('REGISTRATOR_ETCD_NS', '/simple-registrator/')
        key = '{!s}{!s}/{!s}/'.format(ns, image_name, info['Id'])
        logger.debug('Updating {!s} in {!s}'.format(key, self.client))
        self._set(key, None, dir=True, ttl=60)
        self._set(key + 'image_id', info['Image'], ttl=60)
        self._set(key + 'dockerhost_name', self.hostname, ttl=60)
        self._set(key + 'dockerhost_ipv4', self.ipv4, ttl=60)
        if 'Ports' in info['NetworkSettings']:
            for port in info['NetworkSettings']['Ports']:
                if info['NetworkSettings']['Ports'][port] is None:
                    # a port that is not exposed, register it with the containers IP
                    data = {'HostIp': '',
                            'HostPort': port,
                            }
                    self._register_exposed_port(key, port, data)
                for data in info['NetworkSettings']['Ports'][port]:
                    logger.debug('Processing exposed port: {!r}'.format(data))
                    self._register_exposed_port(key, port, data)

    def die(self, info):
        image_name = info['Config']['Image']
        ns = os.environ.get('REGISTRATOR_ETCD_NS', '/simple-registrator/')
        key = '{!s}{!s}/{!s}/'.format(ns, image_name, info['Id'])
        logger.debug('Deleting everything under {!s} in {!s}'.format(key, self.client))
        self._delete(key, recursive=True)

    def _register_exposed_port(self, ns, port, data):
        if 'HostIp' not in data or 'HostPort' not in data:
            return
        hostip = data['HostIp']
        if hostip == '0.0.0.0':
            hostip = self.ipv4
        hostport = data['HostPort']
        if ':' in hostip:
            # guess it is ipv6
            where = '[{!s}]:{!s}'.format(hostip, hostport)
        else:
            where = '{!s}:{!s}'.format(hostip, hostport)
        # port is something like 4711/tcp, replace slash with underscore
        port_key = ns + 'port_{!s}'.format(port.replace('/', '_'))
        self._set(port_key, where, ttl=60)

    def _set(self, key, value, **kwargs):
        logger.debug('Set {!s} = {!s}'.format(key, value))
        self.client.write(key, value, **kwargs)

    def _delete(self, key, **kwargs):
        logger.debug('Delete {!s}'.format(key))
        self.client.delete(key, **kwargs)


@backend(name='log', enabled=False)
class Log(object):

    def __call__(self, *args, **kwargs):
        logger.debug('Docker event:\n{!s}'.format(pprint.pformat(args[0])))


@backend(name='monitor_test')
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
