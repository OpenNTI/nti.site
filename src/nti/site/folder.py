#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.site.folder import Folder

from zope.site.site import LocalSiteManager as _ZLocalSiteManager

from .interfaces import IHostSitesFolder
from .interfaces import IHostPolicyFolder
from .interfaces import IHostPolicySiteManager

@interface.implementer(IHostSitesFolder)
class HostSitesFolder(Folder):
	"""
	Simple container implementation for named host sites.
	"""
	lastSynchronized = 0

@interface.implementer(IHostPolicyFolder)
class HostPolicyFolder(Folder):
	"""
	Simple container implementation for the named host site.
	"""

	def __str__(self):
		return 'HostPolicyFolder(%s)' % self.__name__
	
	def __repr__(self):
		return 'HostPolicyFolder(%s,%s)' % (self.__name__,id(self))

@interface.implementer(IHostPolicySiteManager)
class HostPolicySiteManager(_ZLocalSiteManager):
	pass
