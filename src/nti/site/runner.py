#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helpers for running jobs in specific sites.

"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

import warnings


from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from ZODB.interfaces import IDatabase

from nti.transactions.loop import TransactionLoop

from nti.site.interfaces import SiteNotInstalledError

from nti.site.interfaces import ITransactionSiteNames
from nti.site.interfaces import ISiteTransactionRunner

from nti.site.site import get_site_for_site_names

logger = __import__('logging').getLogger(__name__)


# transaction >= 2 < 2.1.1 needs text; Transaction 1 wants
# bytes (generally). Transaction 2.1.1 and above will work with either,
# but text is preferred.
def _tx_string(s):
    return s.decode('utf-8', 'replace') if isinstance(s, bytes) else s


class _RunJobInSite(TransactionLoop):

    _connection = None

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

    def run_handler(self, *args, **kwargs): # pylint:disable=arguments-differ
        sitemanc = self._connection.root()[self.root_folder_name]
        # Put into a policy if need be
        sitemanc = get_site_for_site_names(self.site_names, sitemanc)

        with current_site(sitemanc):
            if component.getSiteManager() != sitemanc.getSiteManager():
                raise SiteNotInstalledError("Hooks not installed?")
            return self.handler(*args, **kwargs)

    def setUp(self):
        # After the transaction manager has been put into explicit
        # mode, open the connection. This lets it perform certain
        # optimizations.
        db = component.getUtility(IDatabase)
        self._connection = db.open()

    def tearDown(self):
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None


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

    return _RunJobInSite(
        func,
        retries=retries,
        sleep=sleep,
        site_names=site_names,
        job_name=job_name,
        side_effect_free=side_effect_free,
        root_folder_name=root_folder_name
    )()

run_job_in_site.__doc__ = ISiteTransactionRunner['__call__'].getDoc()
