#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

def registerUtility(registry, *args, **kwargs):
    return registry.registerUtility(*args, **kwargs)


def unregisterUtility(registry, *args, **kwargs):
    kwargs.pop('force', None)
    # force is ignored.
    return registry.unregisterUtility(*args, **kwargs)
