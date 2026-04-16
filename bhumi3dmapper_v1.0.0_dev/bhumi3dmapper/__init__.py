# -*- coding: utf-8 -*-
def classFactory(iface):  # pylint: disable=invalid-name
    from .bhumi3dmapper import Bhumi3DMapper
    return Bhumi3DMapper(iface)
