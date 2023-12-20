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
import copy
import logging

from spaceone.core import config
from spaceone.core.error import ERROR_CONFIGURATION, ERROR_UNKNOWN
from spaceone.core.scheduler.scheduler import IntervalScheduler
from spaceone.core.auth.jwt.jwt_util import JWTUtil
from spaceone.supervisor.service.supervisor_service import SupervisorService

_LOGGER = logging.getLogger(__name__)

__all__ = ["SyncScheduler"]


def _get_domain_id_from_token(token):
    decoded_token = JWTUtil.unverified_decode(token)
    return decoded_token["did"]


class SyncScheduler(IntervalScheduler):
    """SyncScheduler"""

    @staticmethod
    def get_task_metadata_and_params():
        try:
            name = config.get_global("NAME", "")
            hostname = config.get_global("HOSTNAME", "")
            token = config.get_global("TOKEN", "")

            if token == "":
                _LOGGER.error("TOKEN is not configured")
                raise ERROR_CONFIGURATION(key="TOKEN")

            if name == "":
                _LOGGER.error("name is not configured!")
                raise ERROR_CONFIGURATION(key="NAME")

            if hostname == "":
                _LOGGER.error("hostname is not configured!")
                raise ERROR_CONFIGURATION(key="HOSTNAME")

            tags = config.get_global("TAGS", {})
            labels = config.get_global("LABELS", [])
            domain_id = _get_domain_id_from_token(token)

            metadata = {
                "token": token,
                "domain_id": domain_id,
                "service": "supervisor",
                "resource": "Supervisor",
                "verb": "sync_plugins",
            }

            params = {
                "name": name,
                "hostname": hostname,
                "tags": tags,
                "labels": labels,
                "domain_id": domain_id,
            }

            return metadata, params

        except Exception as e:
            _LOGGER.error(f"[check_global_configuration] error: {e}", exc_info=True)
            raise ERROR_UNKNOWN(message=f"[check_global_configuration] error: {e}")

    def create_task(self):
        metadata, params = self.get_task_metadata_and_params()
        supervisor_svc: SupervisorService = SupervisorService(metadata)
        supervisor_svc.sync_plugins(copy.deepcopy(params))

        return []
