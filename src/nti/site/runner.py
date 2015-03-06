#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import warnings
import contextlib

from zope import interface
from zope import component
from zope.component.hooks import site as current_site

from ZODB.interfaces import IDatabase

from .interfaces import SiteNotInstalledError
from .interfaces import ISiteTransactionRunner

from .site import get_site_for_site_names

@contextlib.contextmanager
def _connection_cm():
	"""
	Opens a connection to the default database.
	"""

	db = component.getUtility( IDatabase )
	conn = db.open()
	for c in conn.connections.values():
		c.setDebugInfo("_connection_cm")
	try:
		yield conn
	finally:
		conn.close()

@contextlib.contextmanager
def _site_cm(conn, site_names=()):
	# If we don't sync, then we can get stale objects that
	# think they belong to a closed connection
	# TODO: Are we doing something in the wrong order? Connection
	# is an ISynchronizer and registers itself with the transaction manager,
	# so we shouldn't have to do this manually
	# ... I think the problem was a bad site. I think this can go away.
	#conn.sync()
	# In fact, it must go away; if we sync the conn, we lose the
	# current transaction
	sitemanc = conn.root()['nti.dataserver'] # XXX coupling
	# Put into a policy if need be
	sitemanc = get_site_for_site_names( site_names, site=sitemanc )

	with current_site( sitemanc ):
		if component.getSiteManager() != sitemanc.getSiteManager(): # pragma: no cover
			raise SiteNotInstalledError( "Hooks not installed?" )
		# XXX: Used to do this check...is it really needed?
		# if component.getUtility( interfaces.IDataserver ) is None: # pragma: no cover
		#	raise InappropriateSiteError()
		yield sitemanc

from nti.transactions.transactions import TransactionLoop

class _RunJobInSite(TransactionLoop):

	def __init__( self, *args, **kwargs ):
		self.site_names = kwargs.pop( 'site_names' )
		self.job_name = kwargs.pop( 'job_name' )
		self.side_effect_free = kwargs.pop('side_effect_free')
		super(_RunJobInSite,self).__init__( *args, **kwargs )

	def describe_transaction( self, *args, **kwargs ):
		if self.job_name:
			return self.job_name
		# Derive from the function
		func = self.handler
		note = func.__doc__
		if note:
			note = note.split('\n', 1)[0]
		else:
			note = func.__name__
		return note

	def run_handler( self, conn,  *args, **kwargs ):
		with _site_cm(conn, self.site_names):
			for c in conn.connections.values():
				c.setDebugInfo(self.site_names)
			result = self.handler( *args, **kwargs )

			# Commit the transaction while the site is still current
			# so that any before-commit hooks run with that site
			# (Though this has the problem that after-commit hooks would have an invalid
			# site!)
			# JAM: DISABLED because the pyramid requests never ran like this:
			# they commit after they are done and the site has been removed
			# t.commit()

			return result

	def __call__( self, *args, **kwargs ):
		with _connection_cm() as conn:
			for c in conn.connections.values():
				c.setDebugInfo(self.describe_transaction(*args, **kwargs))
			# Notice we don't keep conn as an ivar anywhere, to avoid
			# any chance of circular references. These need to be sure to be
			# reclaimed
			return super(_RunJobInSite,self).__call__( conn, *args, **kwargs )

_marker = object()

@interface.provider(ISiteTransactionRunner)
def run_job_in_site(func,
					retries=0,
					sleep=None,
					site_names=_marker,
					job_name=None,
					side_effect_free=False):
	"""
	Runs the function given in `func` in a transaction and dataserver local
	site manager. See :class:`.ISiteTransactionRunner`

	:return: The value returned by the first successful invocation of `func`.
	"""

	# site_names is deprecated, we want to start preserving
	# the current site. Because the current site should be based on the
	# current site names FOR NOW, preserving the current site names
	# is equivalent. THIS IS CHANGING though.
	if site_names is not _marker:
		warnings.warn("site_names is deprecated. "
					  "Call this already in the appropriate site",
					  FutureWarning )
	else:
		# This is a bit scuzzy; that's part of why this is going away.
		# Note the nearly-circular import
		from nti.appserver.policies.site_policies import get_possible_site_names
		site_names = get_possible_site_names()

	return _RunJobInSite( func,
						  retries=retries,
						  sleep=sleep,
						  site_names=site_names,
						  job_name=job_name,
						  side_effect_free=side_effect_free)()

run_job_in_site.__doc__ = ISiteTransactionRunner['__call__'].getDoc()
