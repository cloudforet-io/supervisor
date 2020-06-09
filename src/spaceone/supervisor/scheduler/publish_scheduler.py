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

import consul
import logging
import time

from spaceone.core import config
from spaceone.core.error import ERROR_CONFIGURATION
from spaceone.core.scheduler.scheduler import IntervalScheduler
from spaceone.core.auth.jwt.jwt_util import JWTUtil

_LOGGER = logging.getLogger(__name__)


__all__ = ['PublishScheduler']


def _get_domain_id_from_token(token):
    decoded_token = JWTUtil.unverified_decode(token)
    return decoded_token['did']


WAIT_QUEUE_INITIALIZED = 10     # seconds for waiting queue initilization
INTERVAL = 10
MAX_COUNT = 10


def _validate_token(token):
    if isinstance(token, dict):
        protocol = token['protocol']
        if protocol == 'consul':
            consul_instance = Consul(token['config'])
            value = False
            while value is False:
                uri = token['uri']
                value = consul_instance.patch_token(uri)
                _LOGGER.warn(f'[_validate_token] token: {value[:30]} uri: {uri}')
                if value:
                    break
                time.sleep(INTERVAL)

            token = value

    return token


class PublishScheduler(IntervalScheduler):
    """ PublishScheduler
    """
    def check_global_configuration(self):
        try:
            self.name = config.get_global('NAME')
            self.hostname = config.get_global('HOSTNAME')
            self.tags = config.get_global('TAGS')
            self.plugin_config = config.get_global('PLUGIN')
            self.token = config.get_global('TOKEN')
            if self.token == "":
                self.token = _validate_token(config.get_global('TOKEN_INFO'))

            if self.token == "":
                _LOGGER.error("TOKEN is not configured")
                raise ERROR_CONFIGURATION(key='TOKEN')
            if self.name == "":
                _LOGGER.error("name is not configured!")
                raise ERROR_CONFIGURATION(key='NAME')
            if self.hostname == "":
                _LOGGER.error("hostname is not configured!")
                raise ERROR_CONFIGURATION(key='HOSTNAME')
            if self.tags == {}:
                _LOGGER.warn("TAGS is not configured!")

            self.domain_id = _get_domain_id_from_token(self.token)
            return True
        except Exception as e:
            _LOGGER.error(e)
            raise ERROR_CONFIGURATION(key=e)

    def create_task(self):
        self.check_global_configuration()
        metadata = {'token': self.token, 'domain_id': self.domain_id}
        publish_task = {
            'locator': 'SERVICE',
            'name': 'SupervisorService',
            'metadata': metadata,
            'method': 'publish_supervisor',
            'params': {'params': {
                            'name': self.name,
                            'hostname': self.hostname,
                            'tags': self.tags,
                            'domain_id': self.domain_id
                            }
                       }
        }
        return [{'stages': [publish_task]}]


class Consul:
    def __init__(self, config):
        """
        Args:
          - config: connection parameter

        Example:
            config = {
                    'host': 'consul.example.com',
                    'port': 8500
                }
        """
        self.config = self._validate_config(config)

    def _validate_config(self, config):
        """
        Parameter for Consul
        - host, port=8500, token=None, scheme=http, consistency=default, dc=None, verify=True, cert=None
        """
        options = ['host', 'port', 'token', 'scheme', 'consistency', 'dc', 'verify', 'cert']
        result = {}
        for item in options:
            value = config.get(item, None)
            if value:
              result[item] = value
        return result

    def patch_token(self, key):
        """
        Args:
            key: Query key (ex. /debug/supervisor/TOKEN)

        """
        try:
            conn = consul.Consul(**self.config)
            index, data = conn.kv.get(key)
            return data['Value'].decode('ascii')

        except Exception as e:
            return False
