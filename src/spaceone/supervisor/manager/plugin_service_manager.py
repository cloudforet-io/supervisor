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

__all__ = ['PluginServiceManager']

import logging

from spaceone.core import config
from spaceone.core.manager import BaseManager

_LOGGER = logging.getLogger(__name__)


class PluginServiceManager(BaseManager):
    def __init__(self, transaction):
        super().__init__(transaction)

    def publish_supervisor(self, params):
        """ Get connector for plugin

        connector is gRPC client for Plugin Service
        """
        _LOGGER.debug("Manager:publish_supervisor:%s" % params)
        connector = self.locator.get_connector('PluginConnector')
        r = connector.publish(params)
        return r

    def list_plugins(self, supervisor_id, hostname, domain_id):
        """ Sync Plugins from Plugin Service
        """
        connector = self.locator.get_connector('PluginConnector')
        _LOGGER.debug("[supervisor_manager] list_plugin:%s" % hostname)
        r = connector.list_plugins_by_hostname(supervisor_id, hostname, domain_id)
        return r

