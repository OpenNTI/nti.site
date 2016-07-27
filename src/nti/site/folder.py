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

try:
	_subscribed_registration = True

	# XXX: Internal APIs
	from zope.interface.registry import _getName
	from zope.interface.registry import _getUtilityProvided

	from zope.interface.registry import notify
	from zope.interface.registry import Registered
	from zope.interface.registry import Unregistered
	from zope.interface.registry import UtilityRegistration
except ImportError:
	warnings.warn("Internals for zope.interface.registry changed")
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
			self.subscribedUnregisterUtility(reg[0], provided, name)

		self._utility_registrations[(provided, name)] = component, info, factory
		self.utilities.register((), provided, name, component)

		self.utilities.subscribe((), provided, component)

		if event:
			notify(Registered(
				UtilityRegistration(self, provided, name, component, info,
									factory)))
		return True

	def subscribedUnregisterUtility(self, component=None, provided=None, name=u'',
						  			factory=None, event=True, force=False):

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

		try:
			old = self._utility_registrations.get((provided, name))
		except KeyError:
			if not force:
				raise
			old = ()
		else:
			if (old is None) or ((component is not None) and (component != old[0])):
				return False

			if component is None:
				component = old[0]

		# Note that component is now the old thing registered
		try:
			del self._utility_registrations[(provided, name)]
		except KeyError:
			if not force:
				raise
		self.utilities.unregister((), provided, name)
		self.utilities.unsubscribe((), provided, component)

		if event:
			notify(Unregistered(
				UtilityRegistration(self, provided, name, component, *old[1:])
				))

		return True
