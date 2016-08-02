#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

import warnings

def registerUtility(registry, *args, **kwargs):
    return registry.registerUtility(*args, **kwargs)

def unregisterUtility(registry, *args, **kwargs):
    for k in 'event', 'force':
        if k in kwargs:
            kwargs.pop(k, None)
            warnings.warn(
                "unregisterUtility does not take '%s'; it will be dropped soon" % k,
                FutureWarning,
                stacklevel=2)
    return registry.unregisterUtility(*args, **kwargs)
