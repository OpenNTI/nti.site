#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import warnings

from zope import interface

from zope.site.folder import Folder

from zope.site.site import LocalSiteManager as _ZLocalSiteManager

from ZODB.POSException import ConnectionStateError

from nti.site.interfaces import IHostSitesFolder
from nti.site.interfaces import IHostPolicyFolder
from nti.site.interfaces import IHostPolicySiteManager

@interface.implementer(IHostSitesFolder)
class HostSitesFolder(Folder):
    """
    Simple container implementation for named host sites.
    """
    lastSynchronized = 0

    def __repr__(self):
        try:
            return super(HostSitesFolder, self).__repr__()
        except ConnectionStateError:
            return object.__repr__(self)

    def _delitemf(self, key):
        l = self._BTreeContainer__len
        item = self._SampleContainer__data[key]
        del self._SampleContainer__data[key]
        l.change(-1)
        return item

@interface.implementer(IHostPolicyFolder)
class HostPolicyFolder(Folder):
    """
    Simple container implementation for the named host site.
    """

    def __str__(self):
        return 'HostPolicyFolder(%s)' % self.__name__

    def __repr__(self):
        return 'HostPolicyFolder(%s,%s)' % (self.__name__, id(self))

@interface.implementer(IHostPolicySiteManager)
class HostPolicySiteManager(_ZLocalSiteManager):

    def __repr__(self):
        try:
            return super(HostPolicySiteManager, self).__repr__()
        except ConnectionStateError:
            return object.__repr__(self)
