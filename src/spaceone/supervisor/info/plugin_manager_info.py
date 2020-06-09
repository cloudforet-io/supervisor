# -*- coding: utf-8 -*-

__all__ = ['PluginManagerInfo']

import functools
from spaceone.api.plugin.v1 import plugin_manager_pb2
from spaceone.core.pygrpc.message_type import change_struct_type, change_timestamp_type
from spaceone.plugin.model.plugin_model import PluginManager


def PluginManagerInfo(pm_vo: PluginManager):
    info = {
        'plugin_manager_id': pm_vo.plugin_manager_id,
        'name': pm_vo.name,
        'state': pm_vo.state,
        'is_public': pm_vo.is_public,
        'labels': change_struct_type(pm_vo.labels),
        'tags': change_struct_type(pm_vo.tags),
        'created_at': change_timestamp_type(pm_vo.created_at),
        'updated_at': change_timestamp_type(pm_vo.updated_at),
        'domain_id': pm_vo.domain_id
    }
    return plugin_manager_pb2.PluginManagerInfo(**info)

