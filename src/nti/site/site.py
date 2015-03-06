#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.component.hooks import getSite
from zope.component.interfaces import IComponents

from persistent import Persistent

from .transient import TrivialSite
from .transient import HostSiteManager

def find_site_components(site_names):
	"""
	Return an IComponents implementation named for the first virtual site
	found in the sequence of site_names. If no such components can be found,
	returns none.
	"""
	for site_name in site_names:
		if not site_name: # Empty/default. We want the global. This should only ever be at the end
			return None
		components = component.queryUtility( IComponents, name=site_name )
		if components is not None:
			return components
_find_site_components = find_site_components # BWC

def get_site_for_site_names( site_names, site=None ):
	"""
	Return an :class:`ISite` implementation named for the first virtual site
	found in the sequence of site_names. If no such site can be found,
	returns the fallback site.

	Provisional API, public for testing purposes only.

	:param site_names: Sequence of strings giving the virtual host names
		to use.
	:keyword site: If given, this will be the fallback site (and site manager). If
		not given, then the currently installed site will be used.
	"""

	if site is None:
		site = getSite()

	#assert site.getSiteManager().__bases__ == (component.getGlobalSiteManager(),)
	# Can we find a named site to use?
	site_components = _find_site_components( site_names ) if site_names else None # micro-opt to not call if no names
	if site_components:
		# Yes we can.
		site_name = site_components.__name__
		# Do we have a persistent site installed in the database? If yes,
		# we want to use that.
		try:
			pers_site = site['++etc++hostsites'][site_name]
			site = pers_site
		except (KeyError,TypeError):
			# No, nothing persistent, dummy one up.
			# Note that this code path is deprecated now and not
			# expected to be hit.

			# The site components are only a
			# partial configuration and are not persistent, so we need
			# to use two bases to make it work (order matters) (for
			# example, the main site is almost always the
			# 'nti.dataserver' site, where the persistent intid
			# utilities live; the named sites do not have those and
			# cannot have the persistent nti.dataserver as their real
			# base, so the two must be mixed). They are also not
			# traversable.

			# Host comps used to be simple, but now they may be hierarchacl
			#assert site_components.__bases__ == (component.getGlobalSiteManager(),)
			#gsm = site_components.__bases__[0]
			#assert site_components.adapters.__bases__ == (gsm.adapters,)

			# But the current site, when given, must always be the main
			# dataserver site
			assert isinstance( site, Persistent )
			assert isinstance( site.getSiteManager(), Persistent )

			main_site = site
			site_manager = HostSiteManager( main_site.__parent__,
											main_site.__name__,
											site_components,
											main_site.getSiteManager() )
			site = TrivialSite( site_manager )
			site.__parent__ = main_site
			site.__name__ = site_name

	return site

## Legacy notes:
# Opening the connection registered it with the transaction manager as an ISynchronizer.
# Ultimately this results in newTransaction being called on the connection object
# at `transaction.begin` time, which in turn syncs the storage. However,
# when multi-databases are used, the other connections DO NOT get this called on them
# if they are implicitly loaded during the course of object traversal or even explicitly
# loaded by name turing an active transaction. This can lead to extra read conflict errors
# (particularly with RelStorage which explicitly polls for invalidations at sync time).
# (Once a multi-db connection has been used, then the next time it would be sync'd. A multi-db
# connection is associated with the same connection to another database for its lifetime, and
# when open()'d will sync all other such connections. Corrollary: ALWAYS go through
# a connection object to get access to multi databases; never go through the database object itself.)

# As a workaround, we iterate across all the databases and sync them manually; this increases the
# cost of handling transactions for things that do not use the other connections, but ensures
# we stay nicely in sync.

# JAM: 2012-09-03: With the database resharding, evaluating the need for this.
# Disabling it.
#for db_name, db in conn.db().databases.items():
#	__traceback_info__ = i, db_name, db, func
#	if db is None: # For compatibility with databases we no longer use
#		continue
#	c2 = conn.get_connection(db_name)
#	if c2 is conn:
#		continue
#	c2.newTransaction()

# Now fire 'newTransaction' to the ISynchronizers, including the root connection
# This may result in some redundant fires to sub-connections.
