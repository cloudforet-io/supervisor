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

__all__ = ["PluginServiceManager"]

import logging

from spaceone.core import config
from spaceone.core.manager import BaseManager
from spaceone.core.connector.space_connector import SpaceConnector

_LOGGER = logging.getLogger(__name__)


class PluginServiceManager(BaseManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_connector = SpaceConnector(service="plugin")

    def publish_supervisor(self, params: dict) -> dict:
        """Get connector for plugin

        connector is gRPC client for Plugin Service
        """
        _LOGGER.debug("Manager:publish_supervisor")

        # todo modify api and model
        del params["labels"]
        response = self.plugin_connector.dispatch("Supervisor.publish", params)
        return response

    def list_plugins(self, supervisor_id, hostname, domain_id):
        """Sync Plugins from Plugin Service"""
        token = config.get_global("TOKEN")
        params = {"domain_id": domain_id}
        if supervisor_id:
            params["supervisor_id"] = supervisor_id
        if hostname:
            params["hostname"] = hostname

        response = self.plugin_connector.dispatch(
            "Supervisor.list_plugins", params, token=token
        )
        return response
