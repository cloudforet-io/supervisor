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

__all__ = ["PluginConnector"]

import logging

from spaceone.core.connector import BaseConnector
from spaceone.core import pygrpc
from spaceone.core.utils import parse_endpoint
from spaceone.core.error import ERROR_WRONG_CONFIGURATION

_LOGGER = logging.getLogger(__name__)


class PluginConnector(BaseConnector):
    def __init__(self, transaction, config):
        super().__init__(transaction, config)
        _LOGGER.debug("config: %s" % self.config)
        if 'endpoint' not in self.config:
            raise ERROR_WRONG_CONFIGURATION(key='endpoint')

        if len(self.config['endpoint']) > 1:
            raise ERROR_WRONG_CONFIGURATION(key='too many endpoint')

        for (k, v) in self.config['endpoint'].items():
            # parse endpoint
            e = parse_endpoint(v)
            self.protocol = e['scheme']
            if self.protocol == 'grpc':
                # create grpc client
                self.client = pygrpc.client(endpoint="%s:%s" % (e['hostname'], e['port']), version=k)
            elif self.protocol == 'http':
                # TODO:
                pass

    def publish(self, param):
        """ Call Plugin.Supervisor.publish

        Returns: SupervisorInfo
        """
        _LOGGER.debug(param)
        if self.protocol == 'grpc':
            # Try to connect via grpc client
            _LOGGER.debug("param: %s" % param)
            r = self.client.Supervisor.publish(param,
                                               metadata=self.transaction.get_connection_meta())
            return r
        elif self.protocol == 'http':
            raise ERROR_WRONG_CONFIGURATION(key=self.protocol)

    def list_plugins_by_hostname(self, supervisor_id, hostname, domain_id):

        if self.protocol == 'grpc':
            # Try to connect via grpc client
            param = {'domain_id': domain_id}
            if supervisor_id:
                param.update({'supervisor_id': supervisor_id})
            if hostname:
                param.update({'hostname': hostname})

            _LOGGER.debug(f"param: {param}")
            plugins_info = self.client.Supervisor.list_plugins(param,
                                                               metadata=self.transaction.get_connection_meta())
            return plugins_info

        raise ERROR_WRONG_CONFIGURATION(key=self.protocol)
