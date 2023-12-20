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

__all__ = ["SupervisorManager"]

import logging
from typing import Union

from spaceone.core import config
from spaceone.core.manager import BaseManager
from spaceone.core.connector.space_connector import SpaceConnector

from spaceone.supervisor.connector.kubernetes_connector import KubernetesConnector
from spaceone.supervisor.connector.docker_connector import DockerConnector

_LOGGER = logging.getLogger(__name__)


class SupervisorManager(BaseManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # container API backend
        self.backend = config.get_global("BACKEND")
        connectors_conf = config.get_global("CONNECTORS")
        plugin_conf = connectors_conf[self.backend]
        self.port_range = (plugin_conf["start_port"], plugin_conf["end_port"])

    def install_plugin(self, image_uri, labels, ports, name, registry_config):
        """Install Plugin"""
        # determine connector name
        _LOGGER.debug(
            f"[install_plugin] image_uri: {image_uri}, labels: {labels}, ports: {ports}, name: {name},"
            f" registry_config: {registry_config}"
        )
        # connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
        connector = self.locator.get_connector(self.backend)
        r = connector.run(image_uri, labels, ports, name, registry_config)
        return r

    def delete_plugin(self, plugin_id: str, version: str):
        """Delete plugin"""
        labels = [
            f"spaceone.supervisor.plugin_id={plugin_id}",
            f"spaceone.supervisor.plugin.version={version}",
        ]

        target_plugins = self.list_plugins_by_label(labels)
        _LOGGER.debug(f"[delete_plugin] labels: {labels}, target: {target_plugins}")
        # determine connector
        # connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
        connector = self.locator.get_connector(self.backend)
        deleted_count = 0
        for plugin in target_plugins["results"]:
            _LOGGER.debug(f"[delete_plugin] plugin: {plugin}")
            connector.stop(plugin)
            deleted_count += 1
        return deleted_count

    def create_endpoint(self, hostname):
        """Determine endpoint of plugin"""
        pass

    def list_plugins_by_label(self, label: list) -> dict:
        """Discover plugins based on label

        Args:
            label(string, label)
                - spaceone.supervisor.name=<supervisor name>
        """
        filters = {"label": label}
        try:
            # connector = self.locator.get_connector(self.backend, self.plugin_conf)
            connector: Union[
                KubernetesConnector, DockerConnector
            ] = self.locator.get_connector(self.backend)
            data: dict = connector.search(filters=filters)
            return data
        except Exception as e:
            _LOGGER.error("list_plugins_by_label: %s" % filters)
            _LOGGER.error(e)
            return {"total_count": 0, "results": []}

    @staticmethod
    def get_plugin_from_repository(plugin_id: str, domain_id: str) -> dict:
        """Contact to repository service
        Find plugin_info

        """
        # Create Repository Connector
        token = config.get_global("TOKEN")
        repo_connector = SpaceConnector(service="repository", token=token)
        plugin_info = repo_connector.dispatch(
            "Plugin.get", {"plugin_id": plugin_id}, x_domain_id=domain_id
        )
        return plugin_info

    def find_host_port(self):
        """find host port for container port mapping"""
        # connector = self.locator.get_connector(self.backend, config=self.plugin_conf)
        connector = self.locator.get_connector(self.backend)
        used_ports = connector.list_used_ports()
        _LOGGER.debug("Used ports list: %s" % used_ports)
        s, e = self.port_range
        host_ports = set(range(s, e))
        possible_ports = host_ports - used_ports
        _LOGGER.debug("Possible allocated port list: %s" % possible_ports)
        return possible_ports.pop()

    def get_plugin_endpoint(self, name, hostname, host_port):
        """Find the GRPC endpoint of plugin

        Args:

        Return:
            - endpoint: grpc://abc.example.com:50051
        """
        if self.backend == "DockerConnector":
            endpoint = f"grpc://{hostname}:{host_port}"
        elif self.backend == "KubernetesConnector":
            endpoint = f"grpc://{name}.{hostname}:{host_port}"
        else:
            _LOGGER.error(f"[get_plugin_endpoint] undefined backend: {self.backend}")
        return endpoint
