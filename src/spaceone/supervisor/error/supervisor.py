# -*- coding: utf-8 -*-
from spaceone.core.error import *


class ERROR_INSTALL_PLUGINS(ERROR_BASE):
    _message = 'install plugin failed: {plugins}'

class ERROR_DELETE_PLUGINS(ERROR_BASE):
    _message = 'delete plugin failed excluding: {plugins}'
