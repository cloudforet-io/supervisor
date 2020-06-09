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

__all__ = ["KubernetesConnector"]

import logging
import time
import yaml

from kubernetes import client, config

from spaceone.core.error import ERROR_CONFIGURATION

from spaceone.supervisor.connector.container_connector import ContainerConnector

_LOGGER = logging.getLogger(__name__)

# max second for status checking
MAX_COUNT = 300


class KubernetesConnector(ContainerConnector):
    def __init__(self, transaction, conf=None, **kwargs):
        super().__init__(transaction, conf, **kwargs)
        _LOGGER.debug("config: %s" % self.config)
        self.NUM_OF_REPLICAS = 1
        self.namespace = self.config['namespace']

        try:
            config.load_incluster_config()
            conf = client.Configuration()
            conf.proxy = "http://localhost:8080"
        except Exception as e:
            _LOGGER.debug(f'[KubernetesConnector] {e}')
            raise ERROR_CONFIGURATION(key='kubernetes configuration')

    def __del__(self):
        pass

    def search(self, filters):
        count = 0
        plugins_info = []
        _LOGGER.debug("[KubernetesConnector] filters=%s" % filters)
        if 'label' in filters:
            services = self._list_services(filters['label'])
        else:
            services = []
        _LOGGER.debug(services)
        count = len(services)
        for service in services:
            plugin = self._get_plugin_info_from_service(service)
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
        _LOGGER.debug(f'[run] create kubernetes deployment')

        service = self._create_service(labels, name, ports)
        _LOGGER.debug(f'[run] service yml: {service}')
        deployment = self._create_deployment(image, name, labels)
        _LOGGER.debug(f'[run] deployment yml: {deployment}')

        # TODO: seperate Service & Deployment
        try:
            # Create Service
            k8s_core_v1 = client.CoreV1Api()
            resp_svc = k8s_core_v1.create_namespaced_service(
                    body=service, namespace=self.namespace)
            _LOGGER.debug(f'[run] created service: {resp_svc}')

            # Create Deployment
            k8s_apps_v1 = client.AppsV1Api()
            resp_dep = k8s_apps_v1.create_namespaced_deployment(
                    body=deployment, namespace=self.namespace)

            _LOGGER.debug(f'[run] created deployment: {resp_dep}')
            plugin = self._get_plugin_info_from_service(resp_svc)

            _LOGGER.debug(f'[run] plugin: {plugin}')
            return plugin

        except Exception as e:
            _LOGGER.error(f"[run] Failed to create kubernetes Service & Pod")
            _LOGGER.debug(e)
            raise ERROR_CONFIGURATION(key='kubernetes create')

    def stop(self, plugin):
        # TODO: seperate Service & Deployment
        try:
            name = plugin['name']
            # delete_namespaced_service
            k8s_core_v1 = client.CoreV1Api()
            resp_svc = k8s_core_v1.delete_namespaced_service(name, self.namespace)
            _LOGGER.debug(f'[stop] deleted service: {resp_svc}')

            # delete_namespaced_deployment
            k8s_apps_v1 = client.AppsV1Api()
            resp_dep = k8s_apps_v1.delete_namespaced_deployment(name, self.namespace)
            _LOGGER.debug(f'[stop] deleted deployment: {resp_dep}')

            return True
        except Exception as e:
            _LOGGER.error("Failed to stop docker")
            _LOGGER.debug(e)
            # TODO
            raise ERROR_CONFIGURATION(key='docker configuration')

    def _update_state_machine(self, status):
        return "ACTIVE"

    def _create_deployment(self, image, plugin_name, labels):
        """ Create deployment content (dictionary)

        Args:
            param(dict): {
                    'name': ...

        Returns:
            deployment(dict)
        """
        mgmt_labels = self._get_k8s_label(labels)

        deployment = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {
                'name': plugin_name,
                'labels': mgmt_labels
                },
            'spec': {
                'replicas': self.NUM_OF_REPLICAS,
                'selector': {
                    'matchLabels': mgmt_labels
                    },
                'template': {
                    'metadata': {
                        'name': plugin_name,
                        'labels': mgmt_labels
                        },
                    'spec': {
                        'containers': [{
                            'image': image,
                            'name': plugin_name,
                            'imagePullPolicy': 'Always'
                            }]
                        }
                    }
                }
            }
        return deployment

    def _create_service(self, labels, plugin_name, ports):
        """ Create Service content

        Returns:
            Service(dict)
        """
        mgmt_labels = self._get_k8s_label(labels)
        """  Example
            supervisor_name: root
            plugin_name: aws-ec2
            domain_id: domain-1234
        """
        service = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': plugin_name,
                'annotations': labels,
                'labels': mgmt_labels
            },
            'spec': {
                'ports': [{
                    'port': ports['HostPort'], 'targetPort': ports['TargetPort']
                    }],
                'selector': mgmt_labels
            }
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
                           plugin_name: aws-ec2
                           pluigin_id: plugin-885ff2c52a6c

        Annotations:       spaceone.supervisor.name: root
                           spaceone.supervisor.plugin.endpoint: grpc://root-plugin-885ff2c52a6c.dev-supervisor.svc.cluster.local:50051
                           spaceone.supervisor.plugin.image: pyengine/aws-ec2
                           spaceone.supervisor.plugin.version: 1.0
                           spaceone.supervisor.plugin_id: plugin-885ff2c52a6c
        """
        k8s_core_v1 = client.CoreV1Api()
        resp = k8s_core_v1.list_namespaced_service(
                namespace=self.namespace)
        result = []

        # labels
        labels = []
        if isinstance(label, list):
            labels = label
        else:
            labels = [label]

        # k,v = label.split("=")
        _LOGGER.debug(f'[_list_service] labels: {labels}')
        for item in resp.items:
            if hasattr(item.metadata, 'annotations'):
                annotations = item.metadata.annotations
            else:
                annotations = {}
            if self._exist_label_in_annotation(labels, annotations):
                result.append(item)

        _LOGGER.debug(f'[_list_service] services: {result}')
        return result

    def _exist_label_in_annotation(self, labels, annotation):
        """ Check existance of label in annotation
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

    def _get_plugin_info_from_service(self, service):
        """
        service is V1Service object, not dictionary
        """
        # Custom Labels
        labels = service.metadata.annotations
        _LOGGER.debug("[_get_plugin_info_from_service] labels=%s" % labels)

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

        plugin = {
            'plugin_id': plugin_id,
            'image': image,
            'version': version,
            'endpoint': endpoint,
            'labels': labels,
            'name': service.metadata.name,
            'status': self._update_state_machine(service.status)
            }
        _LOGGER.debug(f'[_get_plugin_info_from_service] plugin: {plugin}')
        return plugin

    def _get_k8s_label(self, labels):
        """ make OPS labels for K8S management
            labels = {
              spaceone.supervisor.name: root
              spaceone.supervisor.domain_id: domain-1234
              spaceone.supervisor.plugin.endpoint: grpc://root-plugin-885ff2c52a6c.dev-supervisor.svc.cluster.local:50051
              spaceone.supervisor.plugin.image: pyengine/aws-ec2
              spaceone.supervisor.plugin.version: 1.0
              spaceone.supervisor.plugin.plugin_name: aws-ec2
              spaceone.supervisor.plugin_id: plugin-885ff2c52a6c
            }

            Returns: mgmt_label (dict)
                {
                    supervisor_name: root
                    plugin_name: aws-ec2
                    domain_id: domain-1234
                }
        """
        mgmt_label = {}
        for k, v in labels.items():
            if k == 'spaceone.supervisor.name':
                mgmt_label['supervisor_name'] = v
            elif k == 'spaceone.supervisor.domain_id':
                mgmt_label['domain_id'] = v
            elif k == 'spaceone.supervisor.plugin.plugin_name':
                mgmt_label['plugin_name'] = v
            elif k == 'spaceone.supervisor.plugin.version':
                mgmt_label['version'] = v
        return mgmt_label
