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

__all__ = ['SupervisorManager']

import logging

from spaceone.core import config
from spaceone.core.manager import BaseManager

_LOGGER = logging.getLogger(__name__)


class SupervisorManager(BaseManager):
    def __init__(self, transaction):
        super().__init__(transaction)
        # container API backend
        self.plugin_conf = config.get_global('PLUGIN')
        self.backend = self.plugin_conf['backend']
        self.port_range = (self.plugin_conf['start_port'], self.plugin_conf['end_port'])

    def install_plugin(self, image_uri, labels, ports, name):
        """ Install Plugin
        """
        # determine connector name
        _LOGGER.debug(f'[install_plugin] image_uri: {image_uri}, labels: {labels}, ports: {ports}, name: {name}')
        connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
        r = connector.run(image_uri, labels, ports, name)
        return r

    def delete_plugin(self, plugin_id, version, domain_id):
        """ Delete plugin
        """
        labels = [
            f'spaceone.supervisor.plugin_id={plugin_id}',
            f'spaceone.supervisor.plugin.version={version}',
            f'spaceone.supervisor.domain_id={domain_id}'
        ]

        target_plugins = self.list_plugins_by_label(labels)
        _LOGGER.debug(f'[delete_plugin] labels: {labels}, target: {target_plugins}')
        # determine connector
        connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
        deleted_count = 0
        for plugin in target_plugins['results']:
            _LOGGER.debug(f'[delete_plugin] plugin: {plugin}')
            connector.stop(plugin)
            deleted_count += 1
        return deleted_count

    def create_endpoint(self, hostname):
        """ Determine endpoint of plugin
        """
        pass

    def list_plugins_by_label(self, label):
        """ Discover plugins based on label

        Args:
            label(string, label)
                - spaceone.supervisor.name=<supervisor name>
        """
        filters = {'label': label}
        try:
            connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
            data = connector.search(filters=filters)
            return data
        except Exception as e:
            _LOGGER.error("list_plugins_by_label: %s" % filters)
            _LOGGER.error(e)
            return {'total_count': 0, 'results': []}

    def get_plugin_from_repository(self, plugin_id, domain_id):
        """ Contact to repository service
        Find plugin_info

        """
        # Create Repository Connector
        connector = self.locator.get_connector("RepositoryConnector")
        plugin_info = connector.get_plugin(plugin_id, domain_id)
        return plugin_info

    def find_host_port(self):
        """ find host port for container port mapping
        """
        connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
        used_ports = connector.list_used_ports()
        _LOGGER.debug("Used ports list: %s" % used_ports)
        s, e = self.port_range
        host_ports = set(range(s, e))
        possible_ports = host_ports - used_ports
        _LOGGER.debug("Possible allocated port list: %s" % possible_ports)
        return possible_ports.pop()

    def get_plugin_endpoint(self, name, hostname, host_port):
        """ Find the GRPC endpoint of plugin

        Args:

        Return:
            - endpoint: grpc://abc.example.com:50051
        """
        if self.backend == 'DockerConnector':
            endpoint = f'grpc://{hostname}:{host_port}'
        elif self.backend == 'KubernetesConnector':
            endpoint = f'grpc://{name}.{hostname}:{host_port}'
        else:
            _LOGGER.error(f'[get_plugin_endpoint] undefined backend: {self.backend}')
        return endpoint
