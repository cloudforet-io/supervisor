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
from spaceone.core import queue
from spaceone.core.scheduler.worker import BaseWorker
from spaceone.core.auth.jwt.jwt_util import JWTUtil

_LOGGER = logging.getLogger(__name__)


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
                _LOGGER.warn(f'[_validate_token] token: {value} uri: {uri}')
                if value:
                    break
                time.sleep(INTERVAL)

            token = value

    _LOGGER.debug(f'[_validate_token] token: {token}')
    return token


class PublishWorker(BaseWorker):
    """ Publish worker is single process
    For maintaining the information of supervisor
    """

    def __init__(self, queue):
        super().__init__(queue)
        _LOGGER.debug("Create PublishWorker: %s" % self._name_)
        _LOGGER.debug("Queue name: %s" % self.queue)

        # This is runtime information
        # Check Global Configuration (name, hostname)
        while True:
            if self.check_global_configuration():
                break
            _LOGGER.error("Please set global configuration again")
            time.sleep(1)
        self.runtime = {}

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
            return False 

    def run(self):
        # self.queue is doorbell for this loop
        params = {'name': self.name,
                  'hostname': self.hostname,
                  'tags': self.tags,
                  'domain_id': self.domain_id
                }

        while True:
            # Read from queue
            # Q format is developer's mind
            q = queue.get(self.queue)
            _LOGGER.debug(f"[{self._name_}] Queue: {q}")
       
            # create Service
            # TODO: domain_id
            service = self.locator.get_service("SupervisorService", metadata={'token':self.token, 'domain_id':''})

            _LOGGER.debug(f"[run] meta.token: {self.token}")
            _LOGGER.debug(f"[run] meta.domain_id: {self.domain_id}")
            # call publish to plugin
            try:
                r = service.publish_supervisor(params)
                _LOGGER.debug(r)
            except Exception as e:
                _LOGGER.error(e)
                _LOGGER.error("Fail to call publish")

class UpdateWorker(BaseWorker):
    def __init__(self, queue):
        super().__init__(queue)
        _LOGGER.debug("Create UpdateWorker: %s" % self._name_)
        _LOGGER.debug("Queue name: %s" % self.queue)

        # This is runtime information
        # Check Global Configuration (name, hostname)
        while True:
            if self.check_global_configuration():
                break
            _LOGGER.error("Please set global configuration again")
            time.sleep(1)
        self.runtime = {}

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
            return False 


    def run(self):
        # self.queue is doorbell for this loop
        params = {
          'hostname': self.hostname,
          'name': self.name,
          'domain_id': self.domain_id
        }

        while True:
            q = queue.get(self.queue)
            _LOGGER.debug(f"[{self._name_}] Queue: {q}")

            # Create Service
            service = self.locator.get_service("SupervisorService", metadata={'token':self.token, 'domain_id':''})

            # call list_plugin
            try:
                r = service.sync_plugins(params)
                _LOGGER.debug("[worker] : %s " % r)
                (plugins, total_count) = r['results'], r['total_count']
                if total_count > 0:
                    for plugin in plugins:
                        # install plugin
                        _LOGGER.debug("install: %s" % plugin)
                        param = {
                            'name': self.name,
                            'plugin_id': plugin.plugin_id,
                            'version': plugin.version,
                            'hostname': self.hostname,
                            'domain_id': self.domain_id
                        }
                        _LOGGER.debug(f'[sync_plugin] param: {param}')
                        service.install_plugin(param)

            except Exception as e:
                _LOGGER.error("Failed to call sync_plugins: %s" % e)

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
