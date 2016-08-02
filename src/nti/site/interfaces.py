#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Site interfaces.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.site.interfaces import IFolder
from zope.site.interfaces import ILocalSiteManager

from nti.schema.field import Number

class InappropriateSiteError(LookupError):
    """
    Raised if the installed site is not suitable to work with.

    Currently no code in this package raises this exception.
    """

class SiteNotInstalledError(AssertionError):
    """
    Raised when setting and getting a site do not work.

    This is most often caused by not installing the zope.component hooks.
    """

class IMainApplicationFolder(IFolder):
    """
    The folder representing the application. The set of persistent
    components will be installed beneath this folder, and this
    folder will be an Site (with a site manager).

    This may be the same thing as the root folder. As an implementation
    note, though, this is typically beneath the root folder and named
    something application specific (e.g., "dataserver2").
    """
class IHostPolicyFolder(IFolder):
    """
    A folder that should always have a site manager, and thus is a
    site, representing a policy for the host name. Persistent
    configuration related to that host should reside in this folder.
    """

class IHostPolicySiteManager(ILocalSiteManager):
    """
    A persistent local site manager that is tied to a site name. It should always
    have two bases, a non-persistent global IComponents configured through
    :mod:`z3c.baseregistry` and the persistent main dataserver site manager,
    in that order. This should be the site manager for an :class:`IHostPolicyFolder`
    """

class IHostSitesFolder(IFolder):
    """
    A container for the sites, each of which should be an
    :class:`IHostPolicyFolder`
    """

    lastSynchronized = Number(title=u"The timestamp at which this object was last synchronized .",
                              default=0.0)
    lastSynchronized.setTaggedValue('_ext_excluded_out', True)

class ITransactionSiteNames(interface.Interface):
    """
    An interface for a utility that return a list of the possible site names
    needed whenever transaction is run.
    """

    def __call__(*args, **kwargs):
        "Return the possible site names"

class ISiteTransactionRunner(interface.Interface):
    """
    Something that runs code within a transaction, properly setting up
    the ZODB, persistent site, and its environment.
    """

    def __call__(func, retries=0, sleep=None, site_names=(), side_effect_free=False,
                 root_folder_name='nti.dataserver'):
        """
        Runs the function given in `func` in a transaction and application local
        site manager (defaulting to the current site manager).

        :param function func: A function of zero parameters to run. If
            it has a docstring, that will be used as the transactions
            note. A transaction will be begun before this function
            executes, and committed after the function completes. This
            function may be rerun if retries are requested, so it
            should be prepared for that.

        :keyword int retries: The number of times to retry the
            transaction and execution of `func` if
            :class:`transaction.interfaces.TransientError` is raised
            when committing. Defaults to zero (so the job runs once).
            If you specify None, an implementation-specific
            number of retries will be used.

        :keyword float sleep: If not none, then the greenlet running
            this function will sleep for this long between retry
            attempts.

        :keyword site_names: DEPRECATED. Sequence of strings giving the
            virtual host names to use. If you do not provide this argument,
            then the currently installed site will be maintained when
            the transaction is run. NOTE: The implementation of this
            may maintain either the site names or the actual site
            object.

        :keyword bool side_effect_free: If true (not the default), then
            the function is assummed to have no side effects that need
            to be committed; the transaction runner is free to abort/rollback
            or commit the transaction at its leisure.

        :keyword str root_folder_name: This names the folder that can be found in the
            root of the ZODB that will serve as the starting point to look for the
            persistent named site.

        :return: The value returned by the first successful invocation of `func`.
        """
