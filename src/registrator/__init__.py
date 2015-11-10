import docker
import sys
import logging

from backends import backends

sys.path.append(".")
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    stream=sys.stderr)


docker_client = docker.Client(base_url='unix://var/run/docker.sock')

for event in docker_client.events():
    if 'status' in event:
        status = event['status']
        info = docker_client.inspect_container(container=event['container'])
        for backend in backends:
            if hasattr(backend,status):
                getattr(backend, status)(info)