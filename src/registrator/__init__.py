import docker
import sys
import logging
import json

from backends import get_backends
from builtins import Log

logger = logging.getLogger(__name__)


def _do_status(status, info):
    """
    Call the 'status' callback on all registered backends.

    :param status: 'start', 'stop' or similar
    :param info:
    :return:
    """
    for backend in get_backends():
        cb = None
        if hasattr(backend, status):
            cb = getattr(backend, status)
        if not cb and hasattr(backend, '__call__'):
            cb = backend  # backend has a default __call__ function for all statuses
        if cb and hasattr(cb, '__call__'):
            try:
                logger.debug('Calling backend {!r} status ({!r})'.format(backend, cb))
                cb(info)
            except Exception:
                logger.exception('Backend {!r} failed status'.format(backend))


def main():
    sys.path.append(".")
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s',
                        stream=sys.stderr)

    docker_client = docker.Client(base_url='unix://var/run/docker.sock')

    # on startup, inform all the backends about the already running containers
    for container in docker_client.containers(filters=dict(status='running')):
        _do_status('running', container)

    for event in docker_client.events():
        if isinstance(event, basestring):
            event = json.loads(event)
        for _req in ['status', 'id']:
            if not _req in event:
                logger.debug('No {!r} in event: {!s}'.format(_req, event))
                continue

        logger.debug('Docker id {!r} is now {!r}'.format(event['id'], event['status']))

        if event['status'] == 'destroy':
            # docker inspect won't work on destroyed containers
            continue

        try:
            info = docker_client.inspect_container(container=event['id'])
        except Exception:
            logger.exception('Docker inspect with {!r} failed'.format(event))
            continue
        _do_status(event['status'], info)
