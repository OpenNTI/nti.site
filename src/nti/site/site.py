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
    """
    # Inherit from _LocalAdapterRegistry for maximum compatibility...we are
    # going to swizzle out classes. Also, it makes sure we are ILocation.

    # Interestingly, we are totally fine to switch out the type from dict
    # to BTree. Much of the actual lookup code is implemented in C, but it calls
    # into Python for _uncached_lookup, which stays in pure python.

    #: The family for the provided map. Defaults to 64-bit maps. I.e., long.
    btree_family = family64

    #: The type of BTree to be used for adapter registrations. This generally shouldn't
    #: be changed. In an emergency, it can be set to :class:`dict` to avoid doing any
    #: migrations.
    btree_oo_type = family64.OO.BTree

    #: The size at which the total number of registered adapters will
    #: be switched to a BTree. This defaults to the BTree's maximum bucket
    #: size before it splits. Thus, when we do this, we will wind up with two
    #: new persistent objects.
    btree_provided_threshold = 30

    #: The size at which individual keys in the lookup decision maps
    #: will be switched to BTrees. This defaults to the BTree's default
    #: bucket size.
    btree_map_threshold = 30

    # We want to be careful: Our ``changed()`` method is invoked as
    # part of ``__setstate__``
    # (``PersistentAdapterRegistry.__setstate__`` sets ``__bases__``,
    # which invokes ``changed()``), but we never want to do conversion
    # at that time, we only want to do conversion as part of a normal
    # ``(un)register()`` or ``(un)subscribe`` call. We use a volatile
    # attribute to determine when this is safe to do. But because
    # ``Persistent.__setstate__()`` clears the ``__dict__`` (and that
    # happens before ``PersistentAdapterRegistry.__setstate__`` sets
    # the bases), we invert the sense of the test, leaving the default
    # as false.
    _v_safe_to_convert = False

    def __init__(self, *args, **kwargs):
        # In case of a threshold of 0, let the top-level things be
        # converted now.
        self._v_safe_to_convert = True
        super(BTreeLocalAdapterRegistry, self).__init__(*args, **kwargs)

    def __setstate__(self, state):
        super(BTreeLocalAdapterRegistry, self).__setstate__(state)
        # We can only assert this here, not in the method we're about to call.
        # See ``BTreeLocalSiteManager.__setstate__``.
        assert not self._v_safe_to_convert
        # Calling via the class avoids a nested call to _p_activate() in the
        # pure-Python implementation.
        BTreeLocalAdapterRegistry._btlar_after_setstate(self)

    def _btlar_after_setstate(self):
        # A hook for legacy conversions. See
        # ``BTreeLocalSiteManager.__setstate__``
        self._v_safe_to_convert = True

    # REMEMBER: Always check the type *before* checking the length.
    # Getting the length of a bare BTree is expensive and loads all the
    # buckets into memory.
    # We want to be very careful not to load BTree buckets unless we have to.

    # Recall that when this is used as the `BTreePersistentComponents`
    # `.adapters` attribute, our `_adapters` attribute will have many dictionaries
    # in the list: one for each number of parameters needed for the adapters.
    # When we are the `.utilities`, though, there will only be one
    # map in the list. It will look like this:
    #
    #   [{iface : {name: utility, ...},
    #     iface2: {name: utility, ...},
    #     ...}]
    #
    # When we're adapters, it will look like this:
    #
    #   [ # one argument
    #     {iface: {name: factory},
    #      iface2: {name: factory}},
    #    # two arguments -> two levels
    #    {iface: {iface2: {name, factory}}}
    #   ]
    #
    # _subscribers is similar-ish, but often has only one named level with
    # a length of one
    #
    #    [{iface: {name: (utility,...)}}]
    #
    # With some additional work, we could also replace those tuples with a
    # custom subclass of PersistentList. It would take a subclass because zope.interface
    # does ``mapping.get(u'') + (value,)``, e.g, adding a tuple to it. So we'd need to
    # implement ``__radd__`` and ``__add__``.
    #
    # The only time that  the `.utilities` object actually uses
    # these ``_subscribers`` is to implement ``getAllUtilitiesRegisteredFor``; that's rarely called,
    # right? Maybe rare enough that we could implement a different mechanism that doesn't need to
    # persistently store the whole list at all.

    def _check_and_btree_maps(self, name):
        btree_type = self.btree_oo_type
        byorder = getattr(self, name)
        # Can't use enumerate here, we mutate `byorder`
        for i in range(len(byorder)): # pylint:disable=consider-using-enumerate
            mapping = byorder[i] # {iface : {name: utility, ...}}
            if (not isinstance(mapping, btree_type)
                    and (len(mapping) > self.btree_map_threshold
                         or name == '_subscribers')):
                # _subscribers always becomes a BTree, because its payload is stashed
                # away in immutable tuples
                logger.info("Converting ordered mapping (name=%s len=%d) to %s.",
                            name, len(mapping), btree_type)
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
            # level. (Recall that utilities *only* have one level.)
            replacement_vals = {}
            for iface, registrations in mapping.items():
                if (not isinstance(registrations, btree_type)
                        and len(registrations) > self.btree_map_threshold):
                    logger.info("Converting bucket (k=%s, len=%d) to %s.",
                                iface, len(registrations), btree_type)
                    replacement_vals[iface] = btree_type(registrations)

            if replacement_vals:
                mapping.update(replacement_vals)
                if not isinstance(mapping, btree_type):
                    # This may or may not be a btree, depending on its own size,
                    # so we may need to mark ourself as changed.
                    self._p_changed = True

    def changed(self, originally_changed):
        # If we changed, check and migrate
        if originally_changed is self and self._v_safe_to_convert:
            if (not isinstance(self._provided, self.btree_family.OI.BTree)
                    and len(self._provided) >= self.btree_provided_threshold):
                logger.info("Converting _provided (len=%d) to %s.",
                            len(self._provided), self.btree_family.OI.BTree)
                self._provided = self.btree_family.OI.BTree(self._provided)
                self._p_changed = True
            for name in ('_adapters', '_subscribers'):
                self._check_and_btree_maps(name)
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
    """
    # pylint:disable=too-many-ancestors

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
                # Assigning to ``__class__`` will activate the object, but
                # it will do so using the ``__setstate__`` of the old
                # class (naturally), not the special one of
                # BTreeLocalAdapterRegistry that makes it safe to do conversions;
                # we do that manually.
                #
                # Of course, I lied a bit. The Pure-Python
                # implementation of persistent (e.g., as used on PyPy)
                # actually uses the ``__setstate__`` of the *new*
                # class (because assigning to ``__class__`` doesn't
                # actually activate the object). So
                # ``_btlar_after_setstate`` may get called twice in
                # that implementation. Since swizzling ``__class__``
                # is poorly defined, this may or may not be considered
                # a bug. See
                # https://github.com/zopefoundation/persistent/issues/155
                reg.__class__ = BTreeLocalAdapterRegistry
                reg._btlar_after_setstate()
                if not changed:
                    reg._p_changed = False


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
