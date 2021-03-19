#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of sites and helpers for working with sites.

"""
# NOTE: unicode_literals is NOT imported!!
from __future__ import print_function, absolute_import, division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from BTrees import family64

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.site.site import LocalSiteManager
from zope.site.site import _LocalAdapterRegistry

from zope.interface.interfaces import IComponents

from persistent import Persistent

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

from nti.site.interfaces import ISiteMapping
from nti.site.interfaces import SiteNotFoundError

from nti.site.transient import TrivialSite
from nti.site.transient import HostSiteManager


from zope.component.persistentregistry import PersistentComponents

def get_alternate_site_name(site_name):
    """
    Check for a configured ISiteMapping
    """
    site_mapping = component.queryUtility(ISiteMapping, name=site_name)
    if site_mapping is not None:
        return site_mapping.target_site_name
    return None


def find_site_components(site_names, check_alternate=False):
    """
    Return an (global, registered) :class:`.IComponents` implementation named
    for the first virtual site found in the sequence of *site_names*.
    If no such components can be found, returns none.
    """
    for site_name in site_names:
        if not site_name:  # Empty/default. We want the global. This should only ever be at the end
            return None

        if check_alternate:
            site_name = get_alternate_site_name(site_name)
            if site_name is None:
                continue

        components = component.queryUtility(IComponents, name=site_name)
        if components is not None:
            return components
    return None

_find_site_components = find_site_components  # BWC


def get_site_for_site_names(site_names, site=None):
    """
    Return an :class:`.ISite` implementation named for the first virtual site
    found in the sequence of site_names.

    First, we'll attempt to find the registered persistent site; either given
    by the site name or redirected by a registered :class:`ISiteMapping`
    pointing to a persistent site. Otherwise, we'll look for a site without the
    :class:`ISiteMapping` lookup.

    We'll then look a registered persistent site having the same name as the
    registered global components found for *site_names*, then that site will be
    used. Otherwise, if there is only a registered global components, a
    non-persistent site that incorporates those components in the lookup order
    while still incorporating the current (or provided) site will be returned.

    If no such site or components can be found, returns the fallback
    site (the current or provided *site*).

    :param site_names: Sequence of strings giving the virtual host names
        to use.
    :keyword site: If given, this will be the fallback site (and site manager). If
        not given, then the currently installed site will be used.

    .. versionchanged:: 1.2.0
        Look for a :class:`ISiteMapping` registration to map a
        non-persistent site to a persistent site.
    .. versionchanged:: 1.3.0
        Prioritize :class:`ISiteMapping` so that persistent sites can be mapped
        to other persistent sites.
    """

    if site is None:
        site = getSite()

    # assert site.getSiteManager().__bases__ == (component.getGlobalSiteManager(),)
    # Can we find a named site to use?
    site_components = None
    if site_names:
        # First look for an ISiteMapping
        site_components = find_site_components(site_names, check_alternate=True)
        if not site_components:
            site_components = find_site_components(site_names)
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
            # XXX: This easily produces resolution orders that are
            # inconsistent with C3. See test_site.test_no_persistent_site.
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

class WrongRegistrationTypeError(TypeError):
    """
    Raised if an adapter registration is of the wrong type.

    .. versionchanged:: 1.0.1
       This is no longer raised by this package.
    """

# This used to catch type errors on get() for default comparison,
# but as of BTrees 4.3.2 that no longer happens. The name needs to
# stay around for BWC with existing pickles.
_PermissiveOOBTree = family64.OO.BTree


class BTreeLocalAdapterRegistry(_LocalAdapterRegistry):
    """
    A persistent adapter registry that can switch its internal
    data structures to be more persistent friendly when they get large.

    .. caution::
       This registry doesn't support registrations on bare
       classes. This is because the Implements and Provides objects
       returned on bare classes do not support comparison or equality
       and hence cannot be used in BTrees. (They only hash and compare
       equal to *themselves*; within the same process this works out
       because of aggressive caching on class objects.) Registering a utility
       to provide a bare class is quite hard to do, in any case. Registering
       adapters to require bare classes is easier but generally not a best practice.

    .. versionchanged:: 3.0.0
       No longer converts any data structures as part of mutating this object.
       Instead, uses the support from zope.interface 5.3 and zope.component 5.0
       to specify the data types to use as they are created on demand.

       Existing persistent registries *must* have the ``rebuild()`` method called
       on them as part of a migration. The best way to do that would be through
       the ``rebuild()`` method on their containing :class:`BTreeLocalSiteManager`.
    """
    # Inherit from _LocalAdapterRegistry for maximum compatibility...we are
    # going to swizzle out classes. Also, it makes sure we are ILocation.

    # Interestingly, we are totally fine to switch out the type from dict
    # to BTree. Much of the actual lookup code is implemented in C, but it calls
    # into Python for _uncached_lookup, which stays in pure python.

    #: The family for the provided map. Defaults to 64-bit maps. I.e., long.
    btree_family = family64

    # Override types from PersistentAdapterRegistry
    _providedType = btree_family.OI.BTree
    _mappingType = btree_family.OO.BTree

    def _addValueToLeaf(self, existing_leaf_sequence, new_item):
        if isinstance(existing_leaf_sequence, tuple):
            # We're mutating unmigrated data. This could lead to data loss
            # if we have a situation from previous versions of this class like
            # BTree -> dict -> tuple; that's about to become
            # BTree -> dict -> PersistentList.
            # Mutations of either the dict or PersistentList won't notify the
            # BTree that it needs to persist itself.
            # In the past, the solution to this was to set the BTree conversion threshold
            # to 0 so that the intermediate dict got converted to a BTree, but that's
            # not possible anymore. So just don't allow it.
            raise TypeError("Forbidding mutation of unmigrated data in %r. Call rebuild()."
                            % self)
        return super(BTreeLocalAdapterRegistry, self)._addValueToLeaf(existing_leaf_sequence,
                                                                      new_item)


class BTreePersistentComponents(PersistentComponents):
    """
    Persistent components that will be friendly to ZODB when they get large.

    Note that despite the name, this class is not Persistent, only its
    internal components are.

    .. caution:: This registry doesn't support bare class registrations.
       See :class:`BTreeLocalAdapterRegistry` for details.
    """

    btree_family = family64

    #: The size at which we will switch from maps to BTrees for registered adapters
    #: and registered utilities (individually). This defaults to the maximum size
    #: of a BTree bucket before it splits. Thus, when we do this, we will wind up with at
    #: least two persistent objects.
    btree_threshold = 30

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
        # The registrations are mappings that look like this:
        #
        #   {(iface, name): (utility, '', None)}
        btree_type = self.btree_family.OO.BTree
        mapping = getattr(self, mapping_name)
        if not isinstance(mapping, btree_type) and len(mapping) > self.btree_threshold:
            mapping = btree_type(mapping)
            setattr(self, mapping_name, mapping)
            # NOTE: This class is *NOT* Persistent, but its subclass BTreeLocalSiteManager
            # *is*. That's why __setstate__ is there and not here...it doesn't make much sense here.

    def registerUtility(self, *args, **kwargs):  # pylint:disable=arguments-differ
        result = super(BTreePersistentComponents, self).registerUtility(*args, **kwargs)
        self._check_and_btree_map('_utility_registrations')
        return result

    def registerAdapter(self, *args, **kwargs): # pylint:disable=arguments-differ
        result = super(BTreePersistentComponents, self).registerAdapter(*args, **kwargs)
        self._check_and_btree_map('_adapter_registrations')
        return result


class BTreeLocalSiteManager(BTreePersistentComponents, LocalSiteManager):
    """
    Persistent local site manager that will be friendly to ZODB when they
    get large.

    .. caution:: This registry doesn't support bare class registrations.
       See :class:`BTreeLocalAdapterRegistry` for details.

    .. versionchanged:: 3.0.0
       No longer attempts to change the class of the ``adapters`` and ``utilities``
       objects when reading old pickles.

       Instead, you must call this object's ``rebuild()`` method as part of a migration.
       This method will call ``rebuild()`` on the ``adapters`` and ``utilities`` objects,
       and also reset the ``__bases__`` of this object (to its current bases). The
       order (leaves first or roots first) shouldn't matter, as long as all registries
       in an inheritance hierarchy are committed in a single transaction.

       If we detect old versions of the class that haven't been migrated,
       we log an error.
    """
    # pylint:disable=too-many-ancestors

    def __setstate__(self, state):
        super(BTreeLocalSiteManager, self).__setstate__(state)
        for reg in self.adapters, self.utilities:
            if (not isinstance(reg, BTreeLocalAdapterRegistry)
                    and isinstance(reg, _LocalAdapterRegistry)):
                logger.error(
                    "The LocalSiteManager %r has a sub-object %r that is not yet migrated.",
                    self, reg
                )

    def rebuild(self):
        for reg in self.adapters, self.utilities:
            if (not isinstance(reg, BTreeLocalAdapterRegistry)
                    and isinstance(reg, _LocalAdapterRegistry)):
                reg.__class__ = BTreeLocalAdapterRegistry
            reg.rebuild()
        # Setting our bases will cause new references to our *base's*
        # .adapters and .utilities to be saved in the ZODB. As long as they migrate
        # at the same time, they will get written with their new '__class__', even
        # if they are migrated after us.
        self.__bases__ = self.__bases__


@interface.implementer(ISiteMapping)
class SiteMapping(SchemaConfigured):
    """
    Maps one site to another.

    :raises a :class:`SiteNotFoundError` object if no site found
    """
    target_site_name = None
    createDirectFieldProperties(ISiteMapping)

    def get_target_site(self):
        """
        Returns the target site as defined by this mapping.
        """
        current_site = getSite()
        site_names = (self.target_site_name,)
        result = get_site_for_site_names(site_names, site=current_site)
        if result is current_site:
            # Invalid mapping
            raise SiteNotFoundError("No site found for %s" % self.target_site_name)
        return result


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
