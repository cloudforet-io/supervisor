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

__all__ = ["KubernetesConnector"]

import logging
import time
from kubernetes import client
from kubernetes import config as k8s_config

from spaceone.core.error import ERROR_CONFIGURATION

from spaceone.supervisor.connector.container_connector import ContainerConnector

_LOGGER = logging.getLogger(__name__)

# max second for status checking
MAX_COUNT = 300
WAIT_CREATION = 30
ENDPOINT_INTERVAL = 10


class KubernetesConnector(ContainerConnector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _LOGGER.debug("[KubernetesConnector] config: %s" % self.config)
        self.headless = self.config.get("headless", False)
        self.node_selector = self.config.get("nodeSelector", {})
        self.NUM_OF_REPLICAS = 1
        self.namespace = self.config["namespace"]

        try:
            k8s_config.load_incluster_config()
            conf = client.Configuration()
        except Exception as e:
            _LOGGER.debug(f"[KubernetesConnector] {e}")
            raise ERROR_CONFIGURATION(key="kubernetes configuration")

    def __del__(self):
        pass

    def search(self, filters: dict) -> dict:
        count = 0
        plugins_info = []
        # _LOGGER.debug("[KubernetesConnector] filters=%s" % filters)
        if "label" in filters:
            services = self._list_services(filters["label"])
        else:
            services = []
        # _LOGGER.debug(services)
        count = len(services)
        for service in services:
            plugin = self._get_plugin_info_from_service(service)

            if self.headless:
                endpoints = plugin.get("endpoints", [])
                if len(endpoints) == 0:
                    continue

            plugins_info.append(plugin)

        return {"results": plugins_info, "total_count": count}

    def run(self, image, labels, ports, name, registry_config):
        """Make sure, custom label is exist
        custom labels:
         - spaceone.supervisor.plugin_id
         - spaceone.supervisor.plugin.image
         - spaceone.supervisor.plugin.version
        """

        # ports (dict)
        # {'HostPort':80, 'TargetPort': 8080}
        # Docker API uses like
        # {'8080/tcp': 80}    , expose 8080/tcp to 80 (public)
        _LOGGER.debug(f"[run] create kubernetes deployment")

        resp_svc = self._get_service(labels, name, ports)
        resp_dep = self._get_deployment(labels, name, image, registry_config)

        try:
            # Update endpoints, if needed
            # Wait a little
            # endpoints = self._update_endpoints(name)

            # _LOGGER.debug(f'[run] created deployment: {resp_dep}')
            plugin = self._get_plugin_info_from_service(resp_svc)

            # _LOGGER.debug(f'[run] plugin: {plugin}')
            return plugin

        except Exception as e:
            _LOGGER.error(f"[run] Failed to create kubernetes Service & Pod")
            _LOGGER.debug(e)
            raise ERROR_CONFIGURATION(key="kubernetes create")

    def stop(self, plugin):
        # TODO: seperated Service & Deployment
        try:
            name = plugin["name"]
            # delete_namespaced_service
            k8s_core_v1 = client.CoreV1Api()
            resp_svc = k8s_core_v1.delete_namespaced_service(name, self.namespace)
            _LOGGER.debug(f"[stop] deleted service")

            # delete_namespaced_deployment
            k8s_apps_v1 = client.AppsV1Api()
            resp_dep = k8s_apps_v1.delete_namespaced_deployment(name, self.namespace)
            _LOGGER.debug(f"[stop] deleted deployment")

            return True
        except Exception as e:
            _LOGGER.error("Failed to stop docker")
            _LOGGER.debug(e)
            # TODO
            raise ERROR_CONFIGURATION(key="docker configuration")

    def _get_replica(self, resource_type, plugin_id=None):
        _LOGGER.debug(
            f"[_get_replica] resource_type: {resource_type}, plugin_id: {plugin_id}"
        )

        REPLICA_DIC = self.config.get("replica", {})
        resource_type_with_plugin_id = resource_type
        if plugin_id:
            resource_type_with_plugin_id = f"{resource_type}?{plugin_id}"

        if resource_type_with_plugin_id in REPLICA_DIC:
            return REPLICA_DIC[resource_type_with_plugin_id]
        elif resource_type in REPLICA_DIC:
            return REPLICA_DIC[resource_type]
        else:
            return self.NUM_OF_REPLICAS

    def _get_deployment(self, labels, name, image, registry_config):
        """Create or get Deployment

        Args:
            name: random generated name for service & deployment
        """
        k8s_apps_v1 = client.AppsV1Api()
        try:
            # get deployment
            resp_dep = k8s_apps_v1.read_namespaced_deployment(
                name=name, namespace=self.namespace
            )
            return resp_dep
        except Exception as e:
            _LOGGER.debug(f"[_get_deployment] may not found, {e}")

        # Create Deployment
        try:
            deployment = self._create_deployment(image, name, labels, registry_config)
            resp_dep = k8s_apps_v1.create_namespaced_deployment(
                body=deployment, namespace=self.namespace
            )

            # create is asynchronous, wait a little
            time.sleep(WAIT_CREATION)

            # wait for max 5 minutes
            wait_count = 0
            while (
                k8s_apps_v1.read_namespaced_deployment(
                    name=name, namespace=self.namespace
                ).status.available_replicas
                < 1
            ):
                time.sleep(10)
                wait_count += 10
                if wait_count > 300:
                    _LOGGER.debug(
                        f"[_get_deployment] too much time to create deployment: {name}, {image}"
                    )

            return resp_dep
        except Exception as e:
            _LOGGER.debug(f"[_get_deployment] failed to create deployment, {e}")
            raise ERROR_CONFIGURATION(key="kubernetes configuration")

    def _create_deployment(self, image, name, labels, registry_config):
        """Create deployment content (dictionary)

        Args:
            param(dict): {
                    'name': ...

        Returns:
            deployment(dict)
        """
        mgmt_labels = self._get_k8s_label(labels)
        # _LOGGER.debug(f'mgmt_labels: {mgmt_labels}')
        if "plugin_id" in mgmt_labels:
            plugin_id = mgmt_labels["plugin_id"]
            NUM_OF_REPLICAS = self._get_replica(mgmt_labels["resource_type"], plugin_id)
        else:
            NUM_OF_REPLICAS = self._get_replica(mgmt_labels["resource_type"])

        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "labels": mgmt_labels},
            "spec": {
                "replicas": NUM_OF_REPLICAS,
                "selector": {"matchLabels": mgmt_labels},
                "template": {
                    "metadata": {"name": name, "labels": mgmt_labels},
                    "spec": {
                        "containers": [
                            {
                                "image": image,
                                "name": name,
                                "imagePullPolicy": "IfNotPresent",
                                "ports": [{"containerPort": 50051}],
                                "livenessProbe": {"tcpSocket": {"port": 50051}},
                            }
                        ],
                        "nodeSelector": self.node_selector,
                    },
                },
            },
        }

        if _service_account_name := self.config.get("service_account"):
            deployment["spec"]["template"]["spec"][
                "serviceAccountName"
            ] = _service_account_name

        if _image_pull_secrets := registry_config.get("image_pull_secrets"):
            deployment["spec"]["template"]["spec"]["imagePullSecrets"] = [
                {"name": _image_pull_secrets}
            ]

        if _container_env := self.config.get("env"):
            deployment["spec"]["template"]["spec"]["containers"][0][
                "env"
            ] = _container_env

        if _container_resources := self.config.get("resources"):
            deployment["spec"]["template"]["spec"]["containers"][0][
                "resources"
            ] = _container_resources

        if _volumes := self.config.get("volumes"):
            deployment["spec"]["template"]["spec"]["volumes"] = _volumes

        if _container_volume_mounts := self.config.get("volume_mounts"):
            deployment["spec"]["template"]["spec"]["containers"][0][
                "volumeMounts"
            ] = _container_volume_mounts

        _LOGGER.debug(f"[_create_deployment] deployment: {deployment}")

        return deployment

    def _update_endpoints(self, svc_name):
        if self.headless is False:
            # Do nothing
            return
        endpoints = []
        wait_count = 0
        while wait_count < 300:
            endpoints = self._get_endpoints(svc_name)
            if endpoints != []:
                break
            time.sleep(10)
            wait_count += 10
        return endpoints

    def _get_service(self, label, name, port):
        """Create or Get Service
        Return: service object
        """
        k8s_core_v1 = client.CoreV1Api()
        try:
            # get service
            resp_svc = k8s_core_v1.read_namespaced_service(
                name=name, namespace=self.namespace
            )
            # _LOGGER.debug(f'[run] found service: {resp_svc}')
            return resp_svc
        except Exception as e:
            _LOGGER.debug(f"[_get_service] may be not found, {e}")

        try:
            # Create Service
            service = self._create_service(label, name, port)
            # _LOGGER.debug(f'[run] service yml: {service}')
            resp_svc = k8s_core_v1.create_namespaced_service(
                body=service, namespace=self.namespace
            )
            # _LOGGER.debug(f'[run] created service: {resp_svc}')
            return resp_svc

        except Exception as e:
            _LOGGER.error(f"[run] Failed to create kubernetes Service")
            _LOGGER.debug(e)
            raise ERROR_CONFIGURATION(key="kubernetes configuration")

    def _create_service(self, labels, name, ports):
        """Create Service content

        Returns:
            Service(dict)
        """
        # _LOGGER.debug(f'[_create_service] headless service: {self.headless}')
        mgmt_labels = self._get_k8s_label(labels)
        """  Example
            supervisor_name: root
            plugin_name: aws-ec2
            resource_type: inventory.collector
            domain_id: domain-1234
        """
        if self.headless:
            spec = {
                "ports": [
                    {"port": ports["HostPort"], "targetPort": ports["TargetPort"]}
                ],
                "selector": mgmt_labels,
                "clusterIP": "None",
            }
        else:
            spec = {
                "ports": [
                    {"port": ports["HostPort"], "targetPort": ports["TargetPort"]}
                ],
                "selector": mgmt_labels,
            }

        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "annotations": labels, "labels": mgmt_labels},
            "spec": spec,
        }
        return service

    def _list_services(self, label):
        """
        label(string):
            spaceone.supervisor.name=<supervisor name>
        label(list):
            ['spaceone.supervisor.name=<supervisor name>', 'a=b', ...]

        In K8S service, we put label at Annotation like

        Labels:            name: root
                           pluigin_id: plugin-885ff2c52a6c

        Annotations:       spaceone.supervisor.name: root
                           spaceone.supervisor.plugin.endpoint: grpc://root-plugin-885ff2c52a6c.dev-supervisor.svc.cluster.local:50051
                           spaceone.supervisor.plugin.image: pyengine/aws-ec2
                           spaceone.supervisor.plugin.version: 1.0
                           spaceone.supervisor.plugin_id: plugin-885ff2c52a6c
        """
        k8s_core_v1 = client.CoreV1Api()
        resp = k8s_core_v1.list_namespaced_service(namespace=self.namespace)
        result = []

        # labels
        labels = []
        if isinstance(label, list):
            labels = label
        else:
            labels = [label]

        # k,v = label.split("=")
        # _LOGGER.debug(f'[_list_service] labels: {labels}')
        for item in resp.items:
            if hasattr(item.metadata, "annotations") and isinstance(
                item.metadata.annotations, dict
            ):
                annotations = item.metadata.annotations
            else:
                annotations = {}
            if self._exist_label_in_annotation(labels, annotations):
                result.append(item)

        # _LOGGER.debug(f'[_list_service] services: {result}')
        return result

    def _get_endpoints(self, svc_name):
        """This will be different from service type
        Headless Service: multiple endpoints
        Service: single endpoint
        """

        def _parse_subsets(response):
            subsets = response.subsets

            if subsets is None:
                _LOGGER.debug(
                    f"[_get_endpoints] subsets is None : {response.metadata.name}"
                )
                return []

            addrs = []
            port = None
            endpoints = []
            for subset in subsets:
                addrs = _parse_endpoints(subset.addresses)
                port = _parse_port(subset.ports)
            for addr in addrs:
                endpoint = f"grpc://{addr}:{port}"
                endpoints.append(endpoint)
            return endpoints

        def _parse_endpoints(addresses):
            """Parse list of addresses"""
            result = []
            for address in addresses:
                ip = address.ip
                result.append(ip)
            return result

        def _parse_port(ports):
            result = []
            for port in ports:
                svc_port = port.port
                result.append(svc_port)
            if len(result) == 1:
                return result[0]

        k8s_core_v1 = client.CoreV1Api()
        try:
            response = k8s_core_v1.read_namespaced_endpoints(
                name=svc_name, namespace=self.namespace
            )
            endpoints = _parse_subsets(response)
            # _LOGGER.debug(f'[_get_endpoints] {endpoints}')
            return endpoints
        except Exception as e:
            _LOGGER.error(
                f"[_get_endpoints] failed to get endpoints: {e}", exc_info=True
            )
            return []

    def _get_plugin_info_from_service(self, service):
        """
        service is V1Service object, not dictionary
        """
        # Custom Labels
        labels = service.metadata.annotations
        # _LOGGER.debug("[_get_plugin_info_from_service] labels=%s" % labels)

        if "spaceone.supervisor.plugin_id" in labels:
            plugin_id = labels["spaceone.supervisor.plugin_id"]
        else:
            plugin_id = "Unknown"
        if "spaceone.supervisor.plugin.image" in labels:
            image = labels["spaceone.supervisor.plugin.image"]
        else:
            image = "Unknown"
        if "spaceone.supervisor.plugin.version" in labels:
            version = labels["spaceone.supervisor.plugin.version"]
        else:
            version = "Unknown"
        if "spaceone.supervisor.plugin.endpoint" in labels:
            endpoint = labels["spaceone.supervisor.plugin.endpoint"]
        else:
            endpoint = "Unknown"

        plugin = {
            "plugin_id": plugin_id,
            "image": image,
            "version": version,
            "endpoint": endpoint,
            "labels": labels,
            "name": service.metadata.name,
            "status": self._update_state_machine(service.status),
        }

        if self.headless:
            endpoints = self._get_endpoints(service.metadata.name)
            plugin["endpoints"] = endpoints

        # _LOGGER.debug(f'[_get_plugin_info_from_service] plugin: {plugin}')
        return plugin

    @staticmethod
    def _exist_label_in_annotation(labels, annotation):
        """Check existance of label in annotation
            (Exact match)

        Args:
            labels(list)
            annotation(dict)

        Return:
            True | False
        """
        result = False
        for label in labels:
            k, v = label.split("=")
            if k in annotation and annotation[k] == v:
                result = True
            else:
                # One of labels is not match
                return False
        return result

    @staticmethod
    def _get_k8s_label(labels):
        """make OPS labels for K8S management
        labels = {
          spaceone.supervisor.name: root
          spaceone.supervisor.domain_id: domain-1234
          spaceone.supervisor.plugin.endpoint: grpc://random_string.dev-supervisor.svc.cluster.local:50051
          spaceone.supervisor.plugin.image: pyengine/aws-ec2
          spaceone.supervisor.plugin.version: 1.0
          spaceone.supervisor.plugin_id: plugin-885ff2c52a6c
        }

        Returns: mgmt_label (dict)
            {
                supervisor_name: root
                plugin_id: plugin-aws-ec2
                domain_id: domain-1234
            }
        """
        mgmt_label = {}
        for k, v in labels.items():
            if k == "spaceone.supervisor.name":
                mgmt_label["supervisor_name"] = v
            elif k == "spaceone.supervisor.domain_id":
                mgmt_label["domain_id"] = v
            elif k == "spaceone.supervisor.plugin_id":
                mgmt_label["plugin_id"] = v
            elif k == "spaceone.supervisor.plugin.version":
                mgmt_label["version"] = v
            elif k == "spaceone.supervisor.plugin.resource_type":
                mgmt_label["resource_type"] = v
        return mgmt_label

    @staticmethod
    def _update_state_machine(status):
        return "ACTIVE"
