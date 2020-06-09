# -*- coding: utf-8 -*-
#
#   Copyright 2020 The SpaceONE Authors.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

__all__ = ["DockerConnector"]

import docker
import logging
import time

from spaceone.core.error import ERROR_CONFIGURATION

from spaceone.supervisor.connector.container_connector import ContainerConnector

_LOGGER = logging.getLogger(__name__)

# max second for status checking
MAX_COUNT = 180


class DockerConnector(ContainerConnector):
    def __init__(self, transaction, conf=None, **kwargs):
        super().__init__(transaction, conf, **kwargs)
        _LOGGER.debug(f'[DockerConnector] config: {self.config}')
        try:
            self.client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        except Exception as e:
            _LOGGER.debug(f'[DockerConnector] {e}')
            raise ERROR_CONFIGURATION(key='docker configuration')

    def __del__(self):
        self.client.close()

    def search(self, filters):
        count = 0
        plugins_info = []
        _LOGGER.debug(f'[search] filters: {filters}')
        containers = self.client.containers.list(filters=filters)
        count = len(containers)
        _LOGGER.debug(f'[search] discovered containers: {count}')
        for container in containers:
            # Custom Labels
            labels = container.labels
            _LOGGER.debug("[DockerConnector] labels=%s" % labels)
            if 'spaceone.supervisor.plugin_id' in labels:
                plugin_id = labels['spaceone.supervisor.plugin_id']
            else:
                plugin_id = "Unknown"
            if 'spaceone.supervisor.plugin.image' in labels:
                image = labels['spaceone.supervisor.plugin.image']
            else:
                image = "Unknown"
            if 'spaceone.supervisor.plugin.version' in labels:
                version = labels['spaceone.supervisor.plugin.version']
            else:
                version = "Unknown"
            if 'spaceone.supervisor.plugin.endpoint' in labels:
                endpoint = labels['spaceone.supervisor.plugin.endpoint']
            else:
                endpoint = "Unknown"

            # Ports
            ports = container.attrs['NetworkSettings']['Ports']
            plugin = {
                'docker_id': container.id,
                'plugin_id': plugin_id,
                'image': image,
                'version': version,
                'ports': ports,
                'endpoint': endpoint,
                'labels': container.labels,
                'name': container.name,
                'status': self._update_state_machine(container.status)
                }
            plugins_info.append(plugin)
        return {'results': plugins_info, 'total_count': count}

    def run(self, image, labels, ports, name):
        """ Make sure, custom label is exist
        custom labels:
         - spaceone.supervisor.plugin_id
         - spaceone.supervisor.plugin.image
         - spaceone.supervisor.plugin.version
        """

        # ports (dict)
        # {'HostPort':80, 'TargetPort': 8080}
        # Docker API uses like
        # {'8080/tcp': 80}    , expose 8080/tcp to 80 (public)
        docker_ports = {'%s/tcp' % ports['TargetPort']: int(ports['HostPort'])}
        # command = "/bin/bash -c 'sleep 360'"
        _LOGGER.debug("Create Docker ...")
        try:
            container = self.client.containers.run(image=image, labels=labels, ports=docker_ports,
                                                   name=name, detach=True, auto_remove=True)

            ######################
            # Wait until running
            ######################
            count = 1
            time.sleep(5)
            status = self._get_status(container.id)
            while status != "running":
                time.sleep(1)
                count = count + 1
                status = self._get_status(container.id)
                _LOGGER.debug(f'[run] docker status check: {status}')
                if count > MAX_COUNT:
                    break

            # Get up-to-date information
            container = self.client.containers.get(container.id)
            labels = container.labels
            if 'spaceone.supervisor.plugin_id' in labels:
                plugin_id = labels['spaceone.supervisor.plugin_id']
            else:
                plugin_id = "Unknown"
            if 'spaceone.supervisor.plugin.image' in labels:
                image = labels['spaceone.supervisor.plugin.image']
            else:
                image = "Unknown"
            if 'spaceone.supervisor.plugin.version' in labels:
                version = labels['spaceone.supervisor.plugin.version']
            else:
                version = "Unknown"

            # Ports
            ports = container.attrs['NetworkSettings']['Ports']

            plugin = {
                'docker_id': container.id,
                'plugin_id': plugin_id,
                'image': image,
                'version': version,
                'ports': ports,
                'labels': container.labels,
                'name': container.name,
                'status': self._update_state_machine(container.status)
                }

            return plugin

        except Exception as e:
            _LOGGER.error("Failed to run docker")
            _LOGGER.debug(e)
            # TODO: 
            raise ERROR_CONFIGURATION(key='docker configuration')

    def stop(self, plugin):
        container_id = plugin['docker_id']
        _LOGGER.debug(f'[docker stop] stop & delete {container_id}')
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            container.remove(force=True)
            return True
        except Exception as e:
            _LOGGER.error("Failed to stop docker")
            _LOGGER.debug(e)
            # TODO
            raise ERROR_CONFIGURATION(key='docker configuration')

    def list_used_ports(self):
        """ Find used ports

        Returns:
            - set of port
        """
        containers = self.client.containers.list()
        allocated_ports = []
        for container in containers:
            if 'NetworkSettings' not in container.attrs:
                _LOGGER.debug(f'Skip {container} since no NetworkSettings')
                continue
            if 'Ports' not in container.attrs['NetworkSettings']:
                _LOGGER.debug(f'No Ports: {container}')
                continue

            ports = container.attrs['NetworkSettings']['Ports']
            """
            {'80/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '8111'}]}
            {'50051/tcp': None}
            """
            try:
                for (k, v) in ports.items():
                    if v is None:
                        continue
                    for host_map in v:
                        if 'HostPort' in host_map:
                            allocated_ports.append(int(host_map['HostPort']))
            except Exception as e:
                _LOGGER.error(f'Fail to parse ports information: {ports}, {e}')
                continue
        return set(allocated_ports)

    def _get_status(self, container_id):
        container = self.client.containers.get(container_id)
        return container.status

    def _update_state_machine(self, status):
        if status == 'running':
            return "ACTIVE"
        return "ERROR"
