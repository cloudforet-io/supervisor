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

from spaceone.core.connector import BaseConnector
from spaceone.core import pygrpc
from spaceone.core.utils import parse_endpoint
from spaceone.core.error import ERROR_NOT_IMPLEMENTED


class ContainerConnector(BaseConnector):
    def __init__(self, transaction, config=None, **kwargs):
        super().__init__(transaction, config, **kwargs)

    def search(self, filters):
        raise ERROR_NOT_IMPLEMENTED(name='search')

    def run(self, image, labels, ports, name):
        # Create Container
        raise ERROR_NOT_IMPLEMENTED(name='run')

    def stop(self, container_id):
        # Delete Container
        raise ERROR_NOT_IMPLEMENTED(name='stop')

    def get(self, container_id):
        raise ERROR_NOT_IMPLEMENTED(name='get')

    def list_used_ports(self):
        return set([])
