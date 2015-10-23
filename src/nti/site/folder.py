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

from ZODB.POSException import ConnectionStateError

from .interfaces import IHostSitesFolder
from .interfaces import IHostPolicyFolder
from .interfaces import IHostPolicySiteManager

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

@interface.implementer(IHostPolicyFolder)
class HostPolicyFolder(Folder):
	"""
	Simple container implementation for the named host site.
	"""

	def __str__(self):
		return 'HostPolicyFolder(%s)' % self.__name__

	def __repr__(self):
		return 'HostPolicyFolder(%s,%s)' % (self.__name__, id(self))

try:
	_subscribed_registration = True

	from zope.interface.registry import notify
	from zope.interface.registry import Registered
	from zope.interface.registry import Unregistered
	from zope.interface.registry import UtilityRegistration

	from zope.interface.registry import _getName
	from zope.interface.registry import _getUtilityProvided
except ImportError:
	_subscribed_registration = False

@interface.implementer(IHostPolicySiteManager)
class HostPolicySiteManager(_ZLocalSiteManager):

	def __repr__(self):
		try:
			return super(HostPolicySiteManager, self).__repr__()
		except ConnectionStateError:
			return object.__repr__(self)

	def subscribedRegisterUtility(self, component=None, provided=None, name='',
								  info=u'', event=True, factory=None):

		if not _subscribed_registration:
			return HostPolicySiteManager.registerUtility(self, component, provided,
												 		 name, info, event, factory)

		if factory:
			if component:
				raise TypeError("Can't specify factory and component.")
			component = factory()

		if provided is None:
			provided = _getUtilityProvided(component)

		if name == u'':
			name = _getName(component)

		reg = self._utility_registrations.get((provided, name))
		if reg is not None:
			if reg[:2] == (component, info):
				# already registered
				return
			self.unregisterUtility(reg[0], provided, name)

		self._utility_registrations[(provided, name)] = component, info, factory
		self.utilities.register((), provided, name, component)

		self.utilities.subscribe((), provided, component)

		if event:
			notify(Registered(
				UtilityRegistration(self, provided, name, component, info,
									factory)))
		return True

	def subscribedUnregisterUtility(self, component=None, provided=None, name=u'',
						  			factory=None, event=True):

		if not _subscribed_registration:
			return HostPolicySiteManager.unregisterUtility(self, component, provided,
														   name, factory)

		if factory:
			if component:
				raise TypeError("Can't specify factory and component.")
			component = factory()

		if provided is None:
			if component is None:
				raise TypeError("Must specify one of component, factory and "
								"provided")
			provided = _getUtilityProvided(component)

		old = self._utility_registrations.get((provided, name))
		if (old is None) or ((component is not None) and
							 (component != old[0])):
			return False

		if component is None:
			component = old[0]

		# Note that component is now the old thing registered
		del self._utility_registrations[(provided, name)]
		self.utilities.unregister((), provided, name)
		self.utilities.unsubscribe((), provided, component)
		
		if event:
			notify(Unregistered(
				UtilityRegistration(self, provided, name, component, *old[1:])
				))

		return True
