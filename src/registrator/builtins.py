import os
import etcd
from backends import backend
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
        prefix_s = os.environ.get('REGISTRATOR_ETCD_NAME_STRIP_PREFIXES', 'docker.sunet.se/')
        self.name_strip_prefixes = prefix_s.split(',')
        self.timeout = int(os.environ.get('REGISTRATOR_ETCD_TIMEOUT', '300'))
        self.ns = os.environ.get('REGISTRATOR_ETCD_NS', '/simple-registrator/')

    def start(self, info):
        """
        A new container has been started.

        :param info: Docker inspect of the container.
        :return:
        """
        key = self._get_key(info)

        # Assemble all the data that needs to be periodically stored in etcd
        _write = {
            key + '/image_name': info['Config']['Image'],
            key + '/image_id': info['Image'],
            key + '/dockerhost_name': self.hostname,
            key + '/dockerhost_ipv4': self.ipv4,
        }
        # Record container IP addresses
        if 'IPAddress' in info['NetworkSettings'] and info['NetworkSettings']['IPAddress']:
            _write['ipv4_address'] = info['NetworkSettings']['IPAddress']
        if 'GlobalIPv6Address' in info['NetworkSettings'] and info['NetworkSettings']['GlobalIPv6Address']:
            # info['NetworkSettings']['GlobalIPv6Address'] is '' if IPv6 is not used
            _write['ipv6_address'] = info['NetworkSettings']['GlobalIPv6Address']
        # Gather all ports data
        if 'Ports' in info['NetworkSettings']:
            self._gather_ports_data(key, _write, info['NetworkSettings']['Ports'])
        # Gather data about networks
        if 'Networks' in info['NetworkSettings']:
            self._gather_networks_data(key, _write, info['NetworkSettings']['Networks'])

        # Start a thread that will periodically store the data in etcd. The purpose
        # of the TTL and thread is to have the data disappear if the simple-registrator
        _update_t = EtcdPeriodicUpdater(key, _write, self._set, logger, self.timeout)
        _update_t.start()
        self.threads[info['Id']] = _update_t

    def _gather_ports_data(self, key, _write, ports):
        for port_proto in ports:
            logger.debug('Processing port {!r}'.format(port_proto))
            port, proto = port_proto.split('/')
            if ports[port_proto] is None:
                # List this port as open on the container IP. It is not guaranteed to actually be open though.
                port_key = '{!s}/ports/listed/{!s}/{!s}'.format(key, proto, port)
                _write[port_key] = _write.get('ipv4_address', '')
            else:
                # If it is not None, this is a list of dicts like [{u'HostIp': u'0.0.0.0', u'HostPort': u'2379'}]
                port_key = '{!s}/ports/exposed/{!s}/{!s}'.format(key, proto, port)
                for this in ports[port_proto]:
                    _host_ip = this['HostIp']
                    if _host_ip == '0.0.0.0':
                        _host_ip = self.ipv4
                    _host_port = this['HostPort']
                    _write[port_key + '/host_ip'] = _host_ip
                    _write[port_key + '/host_port'] = _host_port

    def _gather_networks_data(self, key, _write, networks):
        for name, data in networks.items():
            logger.debug('Processing network {!r}'.format(data))
            net_key = '{!s}/networks/{!s}'.format(key, name)
            for src, dst in [('GlobalIPv6Address', 'ipv6_address'),
                             ('IPAddress', 'ipv4_address'),
                             ('MacAddress', 'mac_address'),
                             ('NetworkID', 'network_id')]:
                if src in data and data[src]:
                    _write[net_key + '/' + dst] = data[src]

    def die(self, info):
        """
        A container is shutting down.

        :param info: Docker inspect of the container.
        :return:
        """
        # First, signal the update thread to stop. The thread might be asleep for a while,
        # but will not update etcd again after it wakes up if thread.done is True.
        _update_t = self.threads.get(info['Id'])
        if not _update_t:
            logger.error('Container {!r} not found in our list'.format(info['Id']))
            return
        _update_t.done = True
        del self.threads[info['Id']]

        # Now, remove all keys from etcd without waiting for the update thread to wake up
        key = self._get_key(info)
        self._delete(key, recursive=True)

    def running(self, info):
        """
        This is the status function for containers discovered running when the
        simple registrator starts.

        :param info: Docker inspect of the container.
        :return:
        """
        self.start(info)

    def _get_key(self, info):
        """
        etcd key prefix for this container.

        :param info: Docker inspect of the container.

        :return: etcd key prefix
        :rtype: str | unicode
        """
        name = info['Config']['Image']
        for this in self.name_strip_prefixes:
            if name.startswith(this):
                name = name[len(this):]
        while name.startswith('/'):
            name = name[1:]
        if ':' in name:
            name, tag = name.split(':')
        else:
            tag = 'unknown'
        key = '{!s}{!s}/{!s}/{!s}'.format(self.ns, name, tag, info['Id'])
        return key

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
    """
    Thread for updating data (with TTL) about a container.

    The idea is to not write data without a TTL into etcd, in case the
    registrator or the host it runs on crashes.
    """

    def __init__(self, ns, data, set_function, logger, timeout, **kwargs):
        super(EtcdPeriodicUpdater, self).__init__(**kwargs)

        self.ns = ns
        self.data = data
        self._set = set_function
        self.logger = logger
        self.timeout = timeout
        self.done = False
        logger.info('Registering new docker container: {!s}'.format(ns))
        logger.debug('Entering data for new container into etcd:\n{!r}'.format(data))

    def run(self):
        self._update()
        while not self.done:
            sleep(self.timeout)
            if not self.done:
                self._update()

    def _update(self):
        logger.debug('Updating {!s}:\n{!s}'.format(self.ns, pprint.pformat(self.data)))
        for key, value in self.data.items():
            self._set(key, value, ttl=self.timeout * 2)


@backend(name='log', enabled=False)
class Log(object):

    def __call__(self, *args, **kwargs):
        logger.debug('Docker event:\n{!s}'.format(pprint.pformat(args[0])))
