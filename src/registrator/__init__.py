import os
import sys
import json
import docker
import pprint
import logging

from backends import get_backends
from builtins import Log

logger = logging.getLogger(__name__)


class Docker(object):

    """ Lazy fetching of docker info """
    def __init__(self, logger, level, client, container):
        self.logger = logger
        self.level = level
        self.client = client
        self.container = container
        self._info = None

    @property
    def info(self):
        if not self._info:
            try:
                self._info = self.client.inspect_container(container=self.container)
                if self.level == logging.DEBUG:
                    # avoid expensive pretty printing unless debug is enabled
                    logger.debug('Docker container info:\n{!s}\n'.format(pprint.pformat(self._info)))
            except Exception:
                logger.exception('Docker inspect with {!r} failed'.format(self.container))
        return self._info


def _do_status(status, docker):
    """
    Call the 'status' callback on all registered backends.

    :param status: 'start', 'stop' or similar
    :param docker:
    :return:
    """
    for backend in get_backends():
        cb = None
        if hasattr(backend, status):
            cb = getattr(backend, status)
        try:
            if cb and hasattr(cb, '__call__'):
                logger.debug('Calling backend {!r}:{!s}'.format(backend, status))
                cb(docker.info)
            else:
                if hasattr(backend, '__call__'):
                    # backend has a default __call__ function for all statuses
                    logger.debug('Calling backend {!r} ({!r})'.format(backend, status))
                    backend(status, docker.info)
        except Exception:
            logger.exception('Backend {!r} failed status()'.format(backend))


def main():
    level = logging.INFO
    if '--debug' in sys.argv or os.environ.get('REGISTRATOR_DEBUG'):
        level = logging.DEBUG
    sys.path.append(".")
    logging.basicConfig(level=level,
                        format='%(asctime)s %(levelname)s %(message)s',
                        stream=sys.stderr)

    docker_client = docker.Client(base_url='unix://var/run/docker.sock')

    logger.info('Simple registrator started, listening for docker events')

    # on startup, inform all the backends about the already running containers
    for container in docker_client.containers(filters=dict(status='running')):
        _do_status('running', container)

    for event in docker_client.events():
        if isinstance(event, basestring):
            event = json.loads(event)

        ignore = False
        for _req in ['status', 'id']:
            if _req not in event:
                logger.debug('No {!r} in event: {!s}'.format(_req, event))
                ignore = True
                break
        if not ignore and event.get('Type') == 'image':
            logger.debug('Ignoring event about docker image')
            ignore = True
        if not ignore and event['status'].startswith('exec_'):
            logger.debug('Ignoring exec event')
            ignore = True
        if ignore:
            continue

        logger.info('Docker id {!r} status: {!s}'.format(event['id'], event['status']))

        if event['status'] == 'destroy':
            # docker inspect won't work on destroyed containers
            continue

        if level == logging.DEBUG:
            # avoid expensive pretty printing unless debug is enabled
            logger.debug('Processing event:\n{!s}'.format(pprint.pformat(event)))

        info = Docker(logger, level, docker_client, event['id'])
        _do_status(event['status'], info)


if __name__ == '__main__':
    try:
        if main():
            sys.exit(0)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
