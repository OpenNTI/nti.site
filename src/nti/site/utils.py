#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .interfaces import IHostPolicySiteManager

def registerUtility(registry, component, provided, name, event=True):
        if IHostPolicySiteManager.providedBy(registry):
                return registry.subscribedRegisterUtility(component,
                                                                                                  provided=provided,
                                                                                                  name=name,
                                                                                                  event=event)
        else:
                return registry.registerUtility(component,
                                                                                provided=provided,
                                                                                name=name,
                                                                                event=event)

def unregisterUtility(registry, component=None, provided=None, name=None, 
                                          event=True, force=False):
        if IHostPolicySiteManager.providedBy(registry):
                return registry.subscribedUnregisterUtility(component=component,
                                                                                                        provided=provided,
                                                                                                        name=name,
                                                                                                        event=event,
                                                                                                        force=force)
        else:
                return registry.unregisterUtility(component=component,
                                                                                  provided=provided,
                                                                                  name=name)
