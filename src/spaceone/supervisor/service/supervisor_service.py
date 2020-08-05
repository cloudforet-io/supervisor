# -*- coding: utf-8 -*-
import logging

from datetime import datetime
from google.protobuf.json_format import MessageToDict
from hashids import Hashids

from spaceone.core.error import ERROR_CONFIGURATION
from spaceone.core.service import *
from spaceone.supervisor.error import ERROR_INSTALL_PLUGINS, ERROR_DELETE_PLUGINS
from spaceone.supervisor.manager.supervisor_manager import SupervisorManager
from spaceone.supervisor.manager.plugin_service_manager import PluginServiceManager

_LOGGER = logging.getLogger(__name__)


@authentication_handler
@authorization_handler
@event_handler
class SupervisorService(BaseService):
    def __init__(self, metadata):
        super().__init__(metadata)
        self._supervisor_mgr: SupervisorManager = self.locator.get_manager('SupervisorManager')
        self._plugin_service_mgr: PluginServiceManager = self.locator.get_manager('PluginServiceManager')

    @transaction
    @check_required(['name', 'hostname', 'domain_id'])
    def publish_supervisor(self, params):
        """ request publish
        The params comes from publish worker

        Args:
            params
              - name
              - hostname
              - tags
              - secret_key
              - domain_id

        """
        # collect plugins_info
        result = self.discover_plugins(params['name'])
        plugins_info = result['results']
        count = result['total_count']
        _LOGGER.debug(f'[publish_supervisor] plugins_info: {plugins_info}, count: {count}')
        result = []
        for plugin_info in plugins_info:
            plugin = {
                'plugin_id': plugin_info['plugin_id'],
                'version': plugin_info['version'],
                'state': plugin_info['status'],
                'endpoint': plugin_info['endpoint']
            }
            if 'endpoints' in plugin_info:
                plugin['endpoints'] = plugin_info['endpoints']
            else:
                plugin['endpoints'] = [plugin_info['endpoint']]

            result.append(plugin)
        params2 = params.copy()
        params2['plugin_info'] = result

        _LOGGER.debug(f'[publish_supervisor] params: {params2}')
        result_data = self._plugin_service_mgr.publish_supervisor(params2)
        return result_data

    @transaction
    @check_required(['hostname','name', 'domain_id'])
    def sync_plugins(self, params):
        """ Sync plugins from Plugin Service
        After sync, install plugins if not exist

        Args:
            params (dict): {
              'hostname': str,
              'name': str,
              'domain_id': str
            }
        """

        self._supervisor_mgr = self.locator.get_manager('SupervisorManager')
        # Parameter check
        supervisor_id = params.get('supervisor_id', None)
        hostname = params.get('hostname', None)
        domain_id = params.get('domain_id', None)

        if supervisor_id is None and hostname is None:
            raise ERROR_CONFIGURATION(key='supervisor_id | hostname')

        # list plugins from plugin service
        _LOGGER.debug("Find plugins at %s, %s" % (supervisor_id, hostname))
        try:
            plugins = self._plugin_service_mgr.list_plugins(supervisor_id, hostname, domain_id)
            num_of_plugins = plugins.total_count
            _LOGGER.debug(f'[sync_plugins] num of plugins: {num_of_plugins}')
        except Exception as e:
            _LOGGER.debug(f'[sync_plugins] {e}')
            return False

        print("XXXXXXXXXXXXXXXXXXXXXX Install XXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        try:
            self._install_plugins(plugins.results, params)
        except Exception as e:
            _LOGGER.debug(f'[sync_plugins] fail to install plugins, {e}')
            raise ERROR_INSTALL_PLUGINS(plugins)

        print("XXXXXXXXXXXXXXXXXXXXX Clean-up XXXXXXXXXXXXXXXXXXXXXXXXXXX")
        try:
            self._delete_plugins(plugins.results, params)
        except Exception as e:
            _LOGGER.debug(f'[sync_plugins] fail to delete plugins, {e}')
            raise ERROR_DELETE_PLUGINS(plugins=plugins)

        # Publish Again
        print("XXXXXXXXXXXXXXXXXXXXXXX Publish XXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        try:
            self.publish_supervisor(params)
        except Exception as e:
            _LOGGER.debug(f'[sync_plugins] fail to public {e}')

    def _install_plugins(self, plugins, params):
        """ Install plugin based on plugins

        Args:
            params (dict): {
              'hostname': str,
              'name': str,
              'domain_id': str
            }

        """
        for plugin in plugins:
            dict_plugin = MessageToDict(plugin, preserving_proto_field_name=True)
            dict_plugin.update(params)
            _LOGGER.debug(f'[_install_plugins] plugin_info: {dict_plugin}')
            if not self._exist_plugin(dict_plugin):
                _LOGGER.debug(f'[_install_plugins] params: {params}')
                self.install_plugin(dict_plugin)
                _LOGGER.debug(f'[_install_plugins] installed: {params}')

    def _delete_plugins(self, plugins, params):
        """ Delete plugins excluding plugins
        """
        labels = [f'spaceone.supervisor.name={params["name"]}']
        current_plugins = self._supervisor_mgr.list_plugins_by_label(labels)
        for current_plugin in current_plugins['results']:
            if _is_members(current_plugin, plugins) is False:
                _LOGGER.debug(f'[_delete_plugins] delete plugin: {current_plugin}')
                # Delete current_plugin
                delete_params = {
                    'plugin_id': current_plugin['plugin_id'],
                    'version': current_plugin['version'],
                    'domain_id': params['domain_id']
                }
                self.delete_plugin(delete_params)
            else:
                _LOGGER.debug(f'[_delete_plugins] member plugin: {current_plugin}')

    def _exist_plugin(self, plugin):
        """ Find plugin at local
        """
        labels = [
            f'spaceone.supervisor.name={plugin["name"]}',
            f'spaceone.supervisor.plugin_id={plugin["plugin_id"]}',
            f'spaceone.supervisor.plugin.version={plugin["version"]}'
        ]
        plugins = self._supervisor_mgr.list_plugins_by_label(labels)
        _LOGGER.debug(f'[_exist_plugin]\n {labels}\n{plugins}')
        if plugins['total_count'] > 0:
            return True
        return False

    @check_required(['name', 'plugin_id', 'version', 'hostname', 'domain_id'])
    def install_plugin(self, params):
        """ Install Plugin based on params

        Args:
            params (plugin_info):
              - name: name of supervisor
              - plugin_id: plugin ID
              - version
              - hostname : for updating plugin endpoint

        image is real uri from repository service, since we maintain multiple docker repository
        """
        # Find detailed plugin information 
        plugin_id = params['plugin_id']
        version = params['version']
        domain_id = params['domain_id']
        plugin_info = self._supervisor_mgr.get_plugin_from_repository(plugin_id, domain_id)
        _LOGGER.debug(f'[install_plugin] plugin_info: {plugin_info}')
        # - image_uri
        # based on image, version, contact to repository API
        image_uri = "%s/%s:%s" % (
                plugin_info.registry_url,
                plugin_info.image, version)

        labels = {
            'spaceone.supervisor.name': params['name'],
            'spaceone.supervisor.plugin_id': params['plugin_id'],
            'spaceone.supervisor.domain_id': params['domain_id'],
            'spaceone.supervisor.plugin.plugin_name': plugin_info.name,
            'spaceone.supervisor.plugin.image': plugin_info.image,
            'spaceone.supervisor.plugin.version': params['version'],
            'spaceone.supervisor.plugin.service_type': plugin_info.service_type
        }
        # Determine port mapping
        host_port = self._supervisor_mgr.find_host_port()
        _LOGGER.debug("Choose Host Port: %d" % host_port)

        # ports(dict)
        # {'HostPort':80, 'TargetPort':80}
        # TODO: how to determine host port
        # TODO: target_port (how can we know?)
        target_port = 50051
        ports = {'HostPort': host_port, 'TargetPort': target_port}

        # container name(This will reduce duplicated container)
        name = _create_unique_name()
        # Update plugin endpoint
        endpoint = self._supervisor_mgr.get_plugin_endpoint(name, params['hostname'], host_port)
        labels.update({'spaceone.supervisor.plugin.endpoint': endpoint})

        result_data = self._supervisor_mgr.install_plugin(image_uri, labels, ports, name)
        _LOGGER.debug(f'[install_plugin] installed plugin info: {result_data}')
        # update endpoint
        return result_data

    @check_required(['plugin_id', 'version', 'domain_id'])
    def delete_plugin(self, params):
        """ Delete Plugin

        Args:
            params(dict) = {
                'plugin_id': 'str',
                'version': 'str',
                'domain_id': 'str'
            }

        """
        result_data = self._supervisor_mgr.delete_plugin(
                                    params['plugin_id'],
                                    params['version'],
                                    params['domain_id'])
        _LOGGER.debug(f'[delete_plugin] result: {result_data}')
        return result_data

    def discover_plugins(self, name):
        """ Discover plugins
        """
        label = f'spaceone.supervisor.name={name}'
        _LOGGER.debug(f'[discover_plugins] label: {label}')
        plugins = self._supervisor_mgr.list_plugins_by_label(label)
        return plugins


def _is_members(plugin_info, plugins_vo):
    plugin_id = plugin_info['plugin_id']
    version = plugin_info['version']

    for plugin in plugins_vo:
        if plugin.plugin_id == plugin_id and plugin.version == version:
            return True
    return False


def _create_unique_name():
    """ Create random unique id for endpoint
    """
    hashids = Hashids(salt='_create_unique_name', alphabet='qwertyuioplkjhgfdsazxcvbnm')
    utcnow = datetime.utcnow()
    return hashids.encode(utcnow.year, utcnow.month, utcnow.day, utcnow.hour, utcnow.minute, utcnow.second)
