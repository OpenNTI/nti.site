#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helpers for running jobs in specific sites.

"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import warnings
import contextlib

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from ZODB.interfaces import IDatabase

from nti.site.interfaces import SiteNotInstalledError

from nti.site.interfaces import ITransactionSiteNames
from nti.site.interfaces import ISiteTransactionRunner

from nti.site.site import get_site_for_site_names

@contextlib.contextmanager
def _connection_cm():
    """
    Opens a connection to the default database.
    """
    db = component.getUtility(IDatabase)
    conn = db.open()
    for c in conn.connections.values():
        c.setDebugInfo("_connection_cm")
    try:
        yield conn
    finally:
        conn.close()

@contextlib.contextmanager
def _site_cm(conn, site_names=(), root_folder_name=u'nti.dataserver'):
    # If we don't sync, then we can get stale objects that
    # think they belong to a closed connection
    # TODO: Are we doing something in the wrong order? Connection
    # is an ISynchronizer and registers itself with the transaction manager,
    # so we shouldn't have to do this manually
    # ... I think the problem was a bad site. I think this can go away.
    # conn.sync()
    # In fact, it must go away; if we sync the conn, we lose the
    # current transaction
    sitemanc = conn.root()[root_folder_name]
    # Put into a policy if need be
    sitemanc = get_site_for_site_names(site_names, sitemanc)

    with current_site(sitemanc):
        if component.getSiteManager() != sitemanc.getSiteManager():
            raise SiteNotInstalledError("Hooks not installed?")
        # XXX: Used to do this check...is it really needed?
        # if component.getUtility( interfaces.IDataserver ) is None:
        #   raise InappropriateSiteError()
        yield sitemanc

from nti.transactions.transactions import TransactionLoop

# transaction >= 2 < 2.1.1 needs text; Transaction 1 wants
# bytes (generally). Transaction 2.1.1 and above will work with either.
def _tx_string(s):
    return s.decode('utf-8', 'replace') if isinstance(s, bytes) else s


class _RunJobInSite(TransactionLoop):

    def __init__(self, *args, **kwargs):
        self.site_names = kwargs.pop('site_names')
        self.job_name = kwargs.pop('job_name')
        self.side_effect_free = kwargs.pop('side_effect_free')
        self.root_folder_name = kwargs.pop('root_folder_name')
        super(_RunJobInSite, self).__init__(*args, **kwargs)

    def describe_transaction(self, *args, **kwargs):
        if self.job_name:
            return _tx_string(self.job_name)
        # Derive from the function
        func = self.handler
        name = getattr(func, '__name__', '')
        doc = getattr(func, '__doc__', '')
        if name == '_': # "Anonymous" function; transaction convention
            name = ''
        note = None
        if doc:
            note = ((name + '\n\n') if name else '') + doc
        elif name:
            note = name

        note = _tx_string(note) if note else None

        return note

    def run_handler(self, conn, *args, **kwargs):
        with _site_cm(conn, self.site_names, self.root_folder_name):
            for c in conn.connections.values():
                c.setDebugInfo(self.site_names)
            result = self.handler(*args, **kwargs)

            # Commit the transaction while the site is still current
            # so that any before-commit hooks run with that site
            # (Though this has the problem that after-commit hooks would have an invalid
            # site!)
            # JAM: DISABLED because the pyramid requests never ran like this:
            # they commit after they are done and the site has been removed
            # t.commit()

            return result

    def __call__(self, *args, **kwargs):
        with _connection_cm() as conn:
            for c in conn.connections.values():
                c.setDebugInfo(self.describe_transaction(*args, **kwargs))
            # Notice we don't keep conn as an ivar anywhere, to avoid
            # any chance of circular references. These need to be sure to be
            # reclaimed
            return super(_RunJobInSite, self).__call__(conn, *args, **kwargs)

_marker = object()

def get_possible_site_names(*args, **kwargs):
    """
    Helper to find the most applicable site names.

    This uses the :class:`.ITransactionSiteNames` utility.
    """
    utility = component.queryUtility(ITransactionSiteNames)
    result = utility(*args, **kwargs) if utility is not None else None
    return result

@interface.provider(ISiteTransactionRunner)
def run_job_in_site(func,
                    retries=0,
                    sleep=None,
                    site_names=_marker,
                    job_name=None,
                    side_effect_free=False,
                    root_folder_name=u'nti.dataserver'):
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
                      FutureWarning)
    else:
        site_names = get_possible_site_names()

    return _RunJobInSite( func,
                          retries=retries,
                          sleep=sleep,
                          site_names=site_names,
                          job_name=job_name,
                          side_effect_free=side_effect_free,
                          root_folder_name=root_folder_name)()

run_job_in_site.__doc__ = ISiteTransactionRunner['__call__'].getDoc()
