import docker
import sys
import logging

from backends import backends


def main():
    sys.path.append(".")
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s',
                        stream=sys.stderr)

    docker_client = docker.Client(base_url='unix://var/run/docker.sock')

    def _do_status(status, info):
        for backend in backends:
            if hasattr(backend, status):
                cb = getattr(backend, status)
                if cb and hasattr(cb,'__call__'):
                    cb(info)

    for container in docker_client.containers(filters=dict(status='running')):
        _do_status('running', container)

    for event in docker_client.events():
        if 'status' in event:
            status = event['status']
            info = docker_client.inspect_container(container=event['container'])
            _do_status(status, info)