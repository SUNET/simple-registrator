import os
import etcd
from backends import backend, monitor
from time import sleep
import logging
import pprint
import socket
import threading

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
        self.threads = dict()

    def start(self, info):
        image_name = info['Config']['Image']
        ns = os.environ.get('REGISTRATOR_ETCD_NS', '/simple-registrator/')
        key = '{!s}{!s}/{!s}/'.format(ns, image_name, info['Id'])

        # Assemble all the data that needs to be periodically stored in etcd
        _write = {
            key + 'image_id': info['Image'],
            key + 'dockerhost_name': self.hostname,
            key + 'dockerhost_ipv4': self.ipv4,
        }
        if 'Ports' in info['NetworkSettings']:
            for port in info['NetworkSettings']['Ports']:
                if info['NetworkSettings']['Ports'][port] is None:
                    # a port that is not exposed, register it with the containers IP
                    data = {'HostIp': '',
                            'HostPort': port,
                            }
                    _k, _v = self._format_exposed_port(key, port, data)
                    _write[_k] = _v
                    continue
                for data in info['NetworkSettings']['Ports'][port]:
                    logger.debug('Processing exposed port: {!r}'.format(data))
                    _k, _v = self._format_exposed_port(key, port, data)
                    _write[_k] = _v

        # Start a thread that will periodically store the data in etcd. The purpose
        # of the TTL and thread is to have the data disappear if the simple-registrator
        _update_t = EtcdPeriodicUpdater(key, _write, self._set, logger)
        _update_t.start()
        self.threads[info['Id']] = _update_t

    def die(self, info):
        # First, signal the update thread to stop. The thread might be asleep for a while,
        # but will not update etcd again after it wakes up if thread.done is True.
        _update_t = self.threads[info['Id']]
        _update_t.done = True
        del self.threads[info['Id']]

        # Now, remove all keys from etcd without waiting for the update thread to wake up
        image_name = info['Config']['Image']
        ns = os.environ.get('REGISTRATOR_ETCD_NS', '/simple-registrator/')
        key = '{!s}{!s}/{!s}/'.format(ns, image_name, info['Id'])
        logger.debug('Deleting everything under {!s} in {!s}'.format(key, self.client))
        self._delete(key, recursive=True)

    def running(self, info):
        self.start(info)

    def _format_exposed_port(self, ns, port, data):
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
        return port_key, where

    def _set(self, key, value, **kwargs):
        if 'dir' in kwargs and kwargs['dir']:
            logger.debug('mkdir {!s}: {!r}'.format(key, kwargs))
        else:
            logger.debug('Set {!s} = {!s}'.format(key, value))
        kwargs['prevExists'] = True
        self.client.write(key, value, **kwargs)

    def _delete(self, key, **kwargs):
        logger.debug('Delete {!s}'.format(key))
        self.client.delete(key, **kwargs)


class EtcdPeriodicUpdater(threading.Thread):

    def __init__(self, ns, data, set_function, logger, **kwargs):
        super(EtcdPeriodicUpdater, self).__init__(**kwargs)

        self.ns = ns
        self.data = data
        self._set = set_function
        self.logger = logger
        self.timeout = kwargs.get('timeout', 30)

        self.done = False

    def run(self):
        self._update()
        while not self.done:
            sleep(self.timeout)
            if not self.done:
                self._update()

    def _update(self):
        logger.debug('Updating {!s}:\n{!s}'.format(self.ns, pprint.pformat(self.data)))
        #self._set(self.ns, None, dir=True, ttl=self.timeout * 2)
        for key, value in self.data.items():
            self._set(key, value, ttl=self.timeout * 2)


@backend(name='log', enabled=False)
class Log(object):

    def __call__(self, *args, **kwargs):
        logger.debug('Docker event:\n{!s}'.format(pprint.pformat(args[0])))
