#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
# NOTE: unicode_literals is NOT imported!!
from __future__ import print_function, absolute_import, division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys

from zope.interface.interface import InterfaceClass
from zope import component

from zope.component.hooks import getSite

from zope.component.interfaces import IComponents

from persistent import Persistent

from nti.site.transient import TrivialSite
from nti.site.transient import HostSiteManager

_PYPY = hasattr(sys, 'pypy_version_info')
_DEFAULT_COMPARISON = "Can't use default __cmp__" if _PYPY else "Object has default comparison"

def find_site_components(site_names):
    """
    Return an IComponents implementation named for the first virtual site
    found in the sequence of site_names. If no such components can be found,
    returns none.
    """
    for site_name in site_names:
        if not site_name:  # Empty/default. We want the global. This should only ever be at the end
            return None
        components = component.queryUtility(IComponents, name=site_name)
        if components is not None:
            return components
_find_site_components = find_site_components  # BWC

def get_site_for_site_names(site_names, site=None):
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

    # assert site.getSiteManager().__bases__ == (component.getGlobalSiteManager(),)
    # Can we find a named site to use?
    site_components = find_site_components(site_names) if site_names else None  # micro-opt to not call if no names
    if site_components:
        # Yes we can.
        site_name = site_components.__name__
        # Do we have a persistent site installed in the database? If yes,
        # we want to use that.
        try:
            pers_site = site[u'++etc++hostsites'][site_name]
            site = pers_site
        except (KeyError, TypeError):
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
            # assert site_components.__bases__ == (component.getGlobalSiteManager(),)
            # gsm = site_components.__bases__[0]
            # assert site_components.adapters.__bases__ == (gsm.adapters,)

            # But the current site, when given, must always be the main
            # dataserver site
            assert isinstance(site, Persistent)
            assert isinstance(site.getSiteManager(), Persistent)

            main_site = site
            site_manager = HostSiteManager(main_site.__parent__,
                                            main_site.__name__,
                                            site_components,
                                            main_site.getSiteManager())
            site = TrivialSite(site_manager)
            site.__parent__ = main_site
            site.__name__ = site_name

    return site

def get_component_hierarchy(site=None):
    site = getSite() if site is None else site
    # XXX: This is tightly coupled. Note that we assume that the parent
    # site is a container for the persistent sites.
    # There should never be a good reason to need to know this.
    hostsites = site.__parent__
    site_names = (site.__name__,)
    # XXX: Why is this not the same thing as site.getSiteManager()?
    components = find_site_components(site_names)
    while components is not None:
        try:
            name = components.__name__
            if name in hostsites:
                yield components
                components = components.__parent__
            else:
                break
        except AttributeError:  # pragma: no cover
            break

def get_component_hierarchy_names(site=None, reverse=False):
    # XXX This is tightly coupled and there should almost never
    # be a good reason to know this.
    result = [x.__name__ for x in get_component_hierarchy(site)]
    if reverse:
        result.reverse()
    return result

from zope.component.persistentregistry import PersistentComponents
from zope.site.site import LocalSiteManager
from zope.site.site import _LocalAdapterRegistry
from BTrees import family64

class WrongRegistrationTypeError(TypeError):
    pass

class _PermissiveOOBTree(family64.OO.BTree):

    def get(self, key, default=None):
        "Doesn't raise an error for getting something with default comparison."
        try:
            return super(_PermissiveOOBTree, self).get(key, default)
        except TypeError as e:
            if e.args[0] == _DEFAULT_COMPARISON:
                return default
            raise # pragma: no cover


class BTreeLocalAdapterRegistry(_LocalAdapterRegistry):
    """
    A persistent adapter registry that can switch its internal
    data structures to be more persistent friendly when they get large.

    .. caution:: This registry doesn't support registrations on bare
       classes. This is because the Implements and Provides objects
       returned on bare classes do not support comparison or equality
       and hence cannot be used in BTrees. (They only hash and compare
       equal to *themselves*; within the same process this works out
       because of aggressive caching on class objects.) Registering a utility
       to provide a bare class is quite hard to do, in any case. Registering
       adapters to require bare classes is easier but generally not a best practice.
    """
    # Inherit from _LocalAdapterRegistry for maximum compatibility...we are
    # going to swizzle out classes. Also, it makes sure we are ILocation.

    # Interestingly, we are totally fine to switch out the type from dict
    # to BTree. Much of the actual lookup code is implemented in C, but it calls
    # into Python for _uncached_lookup, which stays in pure python.

    btree_family = family64
    btree_oo_type = _PermissiveOOBTree
    btree_provided_threshold = 5000
    # The map threshold is lower than the provided threshold because it is
    # there are many keys in the map so the overall effect is amplified.
    btree_map_threshold = 2000

    # REMEMBER: Always check the type *before* checking the length.
    # Getting the length of a bare BTree is expensive and loads all the
    # buckets into memory.

    def _check_and_btree_maps(self, byorder):
        btree_type = self.btree_oo_type
        for i in range(len(byorder)):
            mapping = byorder[i]
            if not isinstance(mapping, btree_type) and len(mapping) > self.btree_map_threshold:
                mapping = btree_type(mapping)
                byorder[i] = mapping
                # self._adapters and self._subscribers are both simply
                # of type `list` (not persistent list) so when we make changes
                # to them, we need to set self._p_changed
                self._p_changed = True

            # This is the first level of the decision tree, and thus
            # the least discriminatory. If i is 0, then this is only
            # things that are specifically providing a single interface
            # (Which is the most common in some usages). These maps are thus
            # liable to get to be the biggest. Note that we only replace at this
            # level.
            replacement_vals = {}
            for k, v in mapping.items():
                if not isinstance(v, btree_type) and len(v) > self.btree_map_threshold:
                    replacement_vals[k] = btree_type(v)

            if replacement_vals:
                mapping.update(replacement_vals)
                # This is a btree now, so there's no need to mark
                # self as _p_changed when we change it.
                assert isinstance(mapping, btree_type)


    def register(self, required, provided, name, value):
        """
        Raises :exc:`WrongRegistrationTypeError` if *required* or
        *provided* contains a bare class.
        """
        # Pre-check that there are no bad registrations.
        for r in required:
            if r is not None and not isinstance(r, InterfaceClass):
                raise WrongRegistrationTypeError("Unsupported declaration type in required %s" % r)
        if not isinstance(provided, InterfaceClass):
            raise WrongRegistrationTypeError("Unsupported declaration type in provided %s" % provided)
        return super(BTreeLocalAdapterRegistry, self).register(required, provided, name, value)

    def changed(self, originally_changed):
        # If we changed, check and migrate
        if originally_changed is self:
            if (not isinstance(self._provided, self.btree_family.OI.BTree)
                and len(self._provided) > self.btree_provided_threshold):
                self._provided = self.btree_family.OI.BTree(self._provided)
                self._p_changed = True
            for byorder in self._adapters, self._subscribers:
                self._check_and_btree_maps(byorder)
        super(BTreeLocalAdapterRegistry, self).changed(originally_changed)

class BTreePersistentComponents(PersistentComponents):
    """
    Persistent components that will be friendly to ZODB when they get large.

    Note that despite the name, this class is not Persistent, only its
    internal components are.

    .. caution:: This registry doesn't support bare class registrations.
       See :class:`BTreeLocalAdapterRegistry` for details.
    """

    btree_family = family64
    btree_threshold = 5000

    def _init_registries(self):
        # NOTE: We cannot simply replace these two attributes at runtime
        # or even in a migration (for example, to upgrade from one type to another type)
        # and expect it to work. If we are the base of some other Components
        # or SiteManager, then these attributes have been copied into the __bases__
        # of *its* adapters and utilities. If we swap out our ivar, then the bases
        # will be out of sync and lookup will be broken. (BTreeLocalSiteManager
        # supposedly keeps track of its subs and so it *could* swap out all of them too.)
        self.adapters = BTreeLocalAdapterRegistry()
        self.utilities = BTreeLocalAdapterRegistry()
        self.adapters.__parent__ = self.utilities.__parent__ = self
        self.adapters.__name__ = u'adapters'
        self.utilities.__name__ = u'utilities'

    def _check_and_btree_map(self, mapping_name):
        btree_type = self.btree_family.OO.BTree
        mapping = getattr(self, mapping_name)
        if not isinstance(mapping, btree_type) and len(mapping) > self.btree_threshold:
            mapping = btree_type(mapping)
            setattr(self, mapping_name, mapping)
            # NOTE: This class is *NOT* Persistent, but its subclass BTreeLocalSiteManager
            # *is*. That's why __setstate__ is there and not here...it doesn't make much sense here.

    def registerUtility(self, component=None, provided=None, name=u'', info=u'',
                        event=True, factory=None):
        result = None
        try:
            result = super(BTreePersistentComponents, self).registerUtility(
                component, provided, name, info, event, factory)
        except WrongRegistrationTypeError:
            # Back out our partial state changes
            self.unregisterUtility(component, provided, name, factory)
            raise
        self._check_and_btree_map('_utility_registrations')

        return result

    def registerAdapter(self, *args, **kwargs):
        result = None
        try:
            result = super(BTreePersistentComponents, self).registerAdapter(*args, **kwargs)
        except WrongRegistrationTypeError:
            kwargs.pop('event', None)
            self.unregisterAdapter(*args, **kwargs)
            raise
        self._check_and_btree_map('_adapter_registrations')
        return result

class BTreeLocalSiteManager(BTreePersistentComponents, LocalSiteManager):
    """
    Persistent local site manager that will be friendly to ZODB when they
    get large.

    .. caution:: This registry doesn't support bare class registrations.
       See :class:`BTreeLocalAdapterRegistry` for details.
    """

    def __setstate__(self, state):
        super(BTreeLocalSiteManager, self).__setstate__(state)
        # Graceful migration from older versions of this class.
        # See note in _init_registries for why we can't simply swap these to new
        # ivars. Instead, we adjust their __class__. Note that we'll have to keep doing this
        # forever or until we save a brand new copy of the object, because the class is stored
        # as part of the pickle. Adjusting the class works because we know that the layout
        # is exactly the same. Now, other objects could be awake and active and querying
        # this object under its old class through their own __bases__, but that's ok:
        # our behaviour modification only comes in at write time...which only happens
        # through methods we expose, so we'll get a chance to swizzle the object out.
        for reg in self.adapters, self.utilities:
            if (not isinstance(reg, BTreeLocalAdapterRegistry)
                and isinstance(reg, _LocalAdapterRegistry)):
                # Only do this for classes we know about.
                # Note: In Persistent 4.2.1, pure-python and C handle __class__ differently.
                # Pure-python doesn't set _p_changed, but C does.
                changed = reg._p_changed
                reg.__class__ = BTreeLocalAdapterRegistry
                if not changed:
                    reg._p_changed = False


# Legacy notes:
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
# for db_name, db in conn.db().databases.items():
#   __traceback_info__ = i, db_name, db, func
#   if db is None: # For compatibility with databases we no longer use
#       continue
#   c2 = conn.get_connection(db_name)
#   if c2 is conn:
#       continue
#   c2.newTransaction()

# Now fire 'newTransaction' to the ISynchronizers, including the root connection
# This may result in some redundant fires to sub-connections.
