#!/usr/bin/env python
# -*- coding: utf-8 -*-

__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904
# pylint:disable=too-many-ancestors

from hamcrest import is_
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import contains_exactly as contains
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import none
from hamcrest import not_none
from hamcrest import has_length
does_not = is_not

import unittest
from unittest import mock as fudge

from zope import interface

from zope.interface import ro
from zope.interface import implementedBy
from zope.interface import Interface
from zope.interface.interfaces import ComponentLookupError

from zope.component.hooks import getSite
from zope.component.hooks import setSite
from zope.component.hooks import site as currentSite

from zope.interface.interfaces import IComponents


from zope.component import globalSiteManager as BASE

from z3c.baseregistry.baseregistry import BaseComponents

from nti.site.folder import HostSitesFolder

from nti.site.interfaces import IHostPolicyFolder
from nti.site.subscribers import threadSiteSubscriber
from nti.site.transient import HostSiteManager as HSM
from nti.site.transient import TrivialSite
from nti.site.site import get_site_for_site_names
from nti.site.site import find_site_components
from nti.site.site import get_component_hierarchy
from nti.site.site import get_component_hierarchy_names

from nti.site.tests import SharedConfiguringTestLayer

from nti.testing.matchers import validly_provides
from nti.testing.matchers import is_false
from nti.testing.base import AbstractTestBase

from persistent import Persistent



class IMock(Interface): # pylint:disable=inherit-non-class
    pass

@interface.implementer(IMock)
class MockSite(object):

    __name__ = None
    __parent__ = None

    def __init__(self, site_man=None):
        self.site_man = site_man

    def getSiteManager(self):
        return self.site_man

class IFoo(Interface): # pylint:disable=inherit-non-class
    pass

@interface.implementer(IFoo)
class RootFoo(object):
    pass

class TestSiteSubscriber(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def testProxyHostComps(self):
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))
        host_comps = BaseComponents(BASE, 'example.com', (BASE,))
        host_sm = HSM('example.com', 'siteman', host_comps, pers_comps)
        host_site = MockSite(host_sm)
        host_site.__name__ = host_sm.__name__
        setSite(host_site)

        new_comps = BaseComponents(BASE, 'sub_site', (pers_comps,))
        new_site = MockSite(new_comps)
        new_site.__name__ = new_comps.__name__
        interface.alsoProvides(new_site, IFoo)

        threadSiteSubscriber(new_site, None)

        cur_site = getSite()
        # It should implement the static and dynamic
        # ifaces
        assert_that(cur_site, validly_provides(IFoo))
        assert_that(cur_site, validly_provides(IMock))

        # It should have the marker property
        assert_that(cur_site.getSiteManager(),
                    has_property('host_components',
                                 host_comps))

        assert_that(ro.ro(cur_site.getSiteManager()),
                    contains(
                        # The first entry is synthesized
                        has_property('__name__', new_comps.__name__),
                        pers_comps,
                        # The host comps appear after all the bases
                        # in the ro of the new site
                        host_comps,
                        BASE))

    def testTraverseFailsIntoSiblingSiteExceptHostPolicyFolders(self):
        new_comps = BaseComponents(BASE, 'sub_site', ())
        new_site = MockSite(new_comps)
        new_site.__name__ = new_comps.__name__

        with currentSite(None):
            threadSiteSubscriber(new_site, None)
            # If we walk into a site...
            # ...and then try to walk into a sibling site with no apparent relationship...
            new_comps2 = BaseComponents(BASE, 'sub_site', (new_comps,))
            new_site2 = MockSite(new_comps2)
            new_site2.__name__ = new_comps2.__name__

            # ... and that's allowed, completely replacing the current site...
            threadSiteSubscriber(new_site2, None)
            assert_that(getSite(), is_(same_instance(new_site2)))

            # ... reset ...
            threadSiteSubscriber(new_site, None)
            assert_that(getSite(), is_(same_instance(new_site)))

            # ... if they are both HostPolicyFolders...
            interface.alsoProvides(new_site, IHostPolicyFolder)
            interface.alsoProvides(new_site2, IHostPolicyFolder)
            threadSiteSubscriber(new_site2, None)

            # ... traversal does not change the site
            assert_that(getSite(), is_(same_instance(new_site)))

    def test_components_unregister_on_site_removal(self):
        site_folder = HostSitesFolder()
        new_site = MockSite()
        interface.alsoProvides(new_site, IHostPolicyFolder)
        key = 'new_site_name'
        site_folder[key] = new_site
        new_site_components = BaseComponents(BASE, 'new_site_name', (BASE,))
        current_site_manager = getSite().getSiteManager()
        current_site_manager.registerUtility(new_site_components,
                                             name=key,
                                             provided=IComponents)

        assert_that(current_site_manager.queryUtility(IComponents, name=key),
                    not_none())
        del site_folder[key]
        assert_that(current_site_manager.queryUtility(IComponents, name=key),
                    none())

        # Safe without registered components
        site_folder[key] = new_site
        del site_folder[key]


class TestGetSiteForSiteNames(AbstractTestBase):

    @fudge.patch('nti.site.site.find_site_components')
    def test_no_persistent_site(self, fake_find):
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))
        host_comps = BaseComponents(BASE, 'example.com', (BASE,))
        host_sm = HSM('example.com', 'siteman', host_comps, pers_comps)
        class PersistentTrivialSite(Persistent, TrivialSite):
            pass
        trivial_site = PersistentTrivialSite(host_sm)
        fake_find.return_value = pers_comps

        from zope.interface.ro import C3
        C3.STRICT_IRO = False
        try:
            x = get_site_for_site_names(('',), trivial_site)
        finally:
            C3.STRICT_IRO = C3.ORIG_STRICT_IRO # pylint:disable=no-member

        assert_that(x, is_not(Persistent))
        assert_that(x, is_(TrivialSite))
        assert_that(x.__name__, is_(pers_comps.__name__))

    def test_find_comps_empty(self):
        assert_that(find_site_components(('',)),
                    is_(none()))


class TestGetComponentHierarchy(AbstractTestBase):

    @fudge.patch('nti.site.site.find_site_components')
    def test_get_component_hierarchy(self, fake_find):
        # This is a lousy test, just testing what we already see done, not
        # correct behaviour
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))

        class LocalMockSite(object):
            __parent__ = None
            __name__ = None

            def __init__(self):
                self.__parent__ = {}

        site_comps_1 = BaseComponents(pers_comps, '1', (pers_comps,))
        site_comps_2 = BaseComponents(site_comps_1, '2', (site_comps_1,))

        site = LocalMockSite()
        site.__parent__[site_comps_1.__name__] = site_comps_1
        site.__parent__[site_comps_2.__name__] = site_comps_2

        fake_find.return_value = site_comps_2

        x = list(get_component_hierarchy(site))
        assert_that(x, is_([site_comps_2, site_comps_1]))

        x = list(get_component_hierarchy_names(site))
        assert_that(x, is_(['2', '1']))

        x = list(get_component_hierarchy_names(site, reverse=True))
        assert_that(x, is_(['1', '2']))

from nti.site.site import BTreeLocalSiteManager as BLSM
from nti.site.site import _LocalAdapterRegistry
from nti.site.site import BTreeLocalAdapterRegistry

from ZODB import DB
from ZODB.DemoStorage import DemoStorage
import transaction


from BTrees import family64
OOBTree = family64.OO.BTree
OIBTree = family64.OI.BTree

@interface.implementer(IFoo)
class GlobalUtilityImplementingFoo(object):
    pass

class TestBTreeSiteMan(AbstractTestBase):

    def test_rebuild_swap_class(self):
        base_comps = BLSM(None)
        # replace with "broken"
        base_comps.adapters = _LocalAdapterRegistry()
        base_comps.utilities = _LocalAdapterRegistry()

        sub_comps = BLSM(None)
        sub_comps.adapters = _LocalAdapterRegistry()
        sub_comps.utilities = _LocalAdapterRegistry()

        sub_comps.__bases__ = (base_comps,)

        assert_that(sub_comps.adapters.__bases__, is_((base_comps.adapters,)))
        assert_that(sub_comps.utilities.__bases__, is_((base_comps.utilities,)))

        # Either order works here.
        base_comps.rebuild()
        sub_comps.rebuild()

        # Still in place
        assert_that(sub_comps.adapters.__bases__, is_((base_comps.adapters,)))
        assert_that(sub_comps.utilities.__bases__, is_((base_comps.utilities,)))

        # And they changed type
        assert_that(sub_comps.adapters.__bases__[0], is_(BTreeLocalAdapterRegistry))
        assert_that(sub_comps.utilities.__bases__[0], is_(BTreeLocalAdapterRegistry))
        assert_that(sub_comps.adapters, is_(BTreeLocalAdapterRegistry))
        assert_that(sub_comps.utilities, is_(BTreeLocalAdapterRegistry))


    def _store_base_subs_in_zodb(self, storage):
        # pylint:disable=too-many-statements
        from zope.testing.loggingsupport import InstalledHandler
        from contextlib import contextmanager

        log = InstalledHandler('nti.site.site')
        self.addCleanup(log.uninstall)

        @contextmanager
        def fresh_connection():
            db = DB(storage)
            conn = db.open()
            try:
                yield conn
                transaction.commit()
            finally:
                transaction.abort()
                conn.close()
                # Always close the DB to clear connection object caches.
                db.close()

        base_comps = BLSM(None)
        assert isinstance(base_comps, Persistent)
        base_comps.btree_threshold = 0
        base_comps.__name__ = 'base'
        # replace with "broken"
        base_comps.adapters = _LocalAdapterRegistry()
        base_comps.utilities = _LocalAdapterRegistry()

        sub_comps = BLSM(None)
        sub_comps.__name__ = 'sub'
        base_comps.adapters = _LocalAdapterRegistry()
        base_comps.utilities = _LocalAdapterRegistry()
        sub_comps.__bases__ = (base_comps,)

        def check_subs(sub_comps, base_comps, expected_base_kind=BTreeLocalAdapterRegistry):
            assert_that(sub_comps.adapters.__bases__, is_((base_comps.adapters,)))
            assert_that(sub_comps.utilities.__bases__, is_((base_comps.utilities,)))
            assert_that(sub_comps.utilities.__bases__[0], is_(expected_base_kind))

        check_subs(sub_comps, base_comps, _LocalAdapterRegistry)

        with fresh_connection() as conn:
            conn.root()['base'] = base_comps
            conn.root()['sub'] = sub_comps

        # Mimic what the old BLSM.__setstate__ did and
        # convert the data structures.
        with fresh_connection() as conn:
            root = conn.root()
            sub_comps = root['sub']
            base_comps = root['base']

            base_comps._p_activate()
            logs = str(log)
            log.uninstall()
            self.assertIn('ERROR', logs)
            self.assertIn('The LocalSiteManager', logs)
            self.assertIn('has a sub-object', logs)

            # Either order works here
            base_comps.rebuild()
            sub_comps.rebuild()
            check_subs(sub_comps, base_comps)

            assert_that(base_comps.adapters, is_(BTreeLocalAdapterRegistry))
            assert_that(base_comps.utilities, is_(BTreeLocalAdapterRegistry))

        with fresh_connection() as conn:
            root = conn.root()
            sub_comps = root['sub']
            base_comps = root['base']
            check_subs(sub_comps, base_comps)

            assert_that(base_comps.adapters, is_(BTreeLocalAdapterRegistry))
            assert_that(base_comps.utilities, is_(BTreeLocalAdapterRegistry))
            assert_that(sub_comps.adapters, is_(BTreeLocalAdapterRegistry))
            assert_that(sub_comps.utilities, is_(BTreeLocalAdapterRegistry))

    def test_pickle_setstate_swap_class_zodb(self):
        storage = DemoStorage()

        self._store_base_subs_in_zodb(storage)

        db = DB(storage)
        conn = db.open()
        new_base = conn.root()['base']
        new_base._p_activate()
        new_sub = conn.root()['sub']

        # Still in place
        assert_that(new_sub.adapters.__bases__, is_((new_base.adapters,)))
        assert_that(new_sub.utilities.__bases__, is_((new_base.utilities,)))

        # And they changed type
        assert_that(new_sub.adapters.__bases__[0], is_(BTreeLocalAdapterRegistry))
        assert_that(new_sub.utilities.__bases__[0], is_(BTreeLocalAdapterRegistry))

        # But p_changed wasn't set.
        assert_that(new_sub.adapters.__bases__[0],
                    has_property('_p_changed', is_false()))

        transaction.commit()
        conn.close()
        db.close()

        db = DB(storage)
        conn = db.open()
        new_sub = conn.root()['sub']
        # Now, we didn't rewrite the reference so the type stayed the same
        assert_that(type(new_sub.adapters.__bases__[0]), _LocalAdapterRegistry)
        assert_that(new_sub.adapters.__bases__[0],
                    has_property('_p_changed', is_false()))

        # Loading the base changes the types
        new_base = conn.root()['base']
        assert_that(new_base.adapters, is_(BTreeLocalAdapterRegistry))
        assert_that(new_base.adapters,
                    same_instance(new_sub.adapters.__bases__[0]))
        assert_that(new_sub.adapters.__bases__[0], is_(BTreeLocalAdapterRegistry))

        assert_that(new_sub.adapters.__bases__[0],
                    has_property('_p_changed', is_false()))

    def test_pickle_zodb_lookup_adapter(self):
        # Now, we can register a couple adapters in the base, save everything,
        # and look it up in the sub (when the classes don't match)
        storage = DemoStorage()
        self._store_base_subs_in_zodb(storage)

        db = DB(storage)
        conn = db.open()
        new_base = conn.root()['base']
        new_base._p_activate()
        new_sub = conn.root()['sub']

        # Note: this used-to cause btree-ing the map to fail. The
        # implementedBy callable previously had default comparison and can't be
        # stored in a btree. As of zope.interface 4.3.0, this is fixed.
        new_base.registerAdapter(_foo_factory,
                                 required=(object,),
                                 provided=IFoo)

        new_base.registerAdapter(_foo_factory2,
                                 required=(IFoo,),
                                 provided=IMock)

        assert_that(new_base._adapter_registrations, is_(OOBTree))
        assert_that(new_base._adapter_registrations.keys(),
                    contains(
                        ((IFoo,), IMock, ''),
                        ((implementedBy(object),), IFoo, ''),
                    ))
        assert_that(new_base.adapters._provided, is_(OIBTree))
        assert_that(new_base.adapters._adapters[0], is_(OOBTree))

        assert_that(new_base.adapters._adapters[1][IFoo], is_(OOBTree))


        new_base.registerAdapter(_foo_factory2,
                                 required=(IFoo,),
                                 provided=IFoo)

        assert_that(new_base.adapters._adapters[1][IFoo], is_(OOBTree))

        transaction.commit()
        conn.close()
        db.close()

        db = DB(storage)
        conn = db.open()
        new_sub = conn.root()['sub']

        x = new_sub.queryAdapter(RootFoo(), IMock)
        assert_that(x, is_(2))

    def test_register_implemented_by_lookup_utility(self):
        storage = DemoStorage()
        self._store_base_subs_in_zodb(storage)

        db = DB(storage)
        conn = db.open()
        new_base = conn.root()['base']
        new_base._p_activate()
        new_sub = conn.root()['sub']

        new_base.registerUtility(MockSite(),
                                 provided=IFoo)
        provided1 = new_base.adapters._provided
        # In the past, we couldn't register by implemented, but now we can.
        new_base.registerUtility(MockSite(),
                                 provided=implementedBy(MockSite),
                                 name='foo')

        provided2 = new_base.adapters._provided
        # Make sure that it only converted once
        assert_that(provided1, is_(same_instance(provided2)))
        assert_that(new_base._utility_registrations, is_(OOBTree))

        assert_that(new_base._utility_registrations.keys(),
                    contains(
                        (IFoo, ''),
                        ((implementedBy(MockSite), 'foo')),
                    ))
        assert_that(new_base.utilities._provided, is_(OIBTree))
        assert_that(new_base.utilities._adapters[0], is_(OOBTree))

        assert_that(new_base.utilities._adapters[0][IFoo], is_(OOBTree))


        transaction.commit()
        conn.close()
        db.close()

        db = DB(storage)
        conn = db.open()
        new_sub = conn.root()['sub']

        x = new_sub.queryUtility(IFoo)
        assert_that(x, is_(MockSite))

        # But it can't actually be looked up, regardless of whether we
        # convert to btrees or not
        x = new_sub.queryUtility(MockSite, 'foo')
        assert_that(x, is_(none()))

    def test_pickle_zodb_lookup_utility(self):
        # Now, we can register a couple utilities in the base, save everything,
        # and look it up in the sub (when the classes don't match)
        storage = DemoStorage()
        self._store_base_subs_in_zodb(storage)

        db = DB(storage)
        conn = db.open()
        new_base = conn.root()['base']
        new_base._p_activate()
        new_sub = conn.root()['sub']

        new_base.registerUtility(MockSite(),
                                 provided=IFoo)
        provided1 = new_base.adapters._provided
        # Previously this would fail. Now it works.
        new_base.registerUtility(MockSite(),
                                 provided=implementedBy(object),
                                 name='foo')

        new_base.registerUtility(MockSite(),
                                 provided=IMock,
                                 name='foo')

        provided2 = new_base.adapters._provided
        # Make sure that it only converted once
        assert_that(provided1, is_(same_instance(provided2)))
        assert_that(new_base._utility_registrations, is_(OOBTree))

        assert_that(new_base._utility_registrations.keys(),
                    contains(
                        (IFoo, ''),
                        (IMock, 'foo'),
                        (implementedBy(object), 'foo'),
                    ))
        assert_that(new_base.utilities._provided, is_(OIBTree))
        assert_that(new_base.utilities._adapters[0], is_(OOBTree))

        assert_that(new_base.utilities._adapters[0][IFoo], is_(OOBTree))


        transaction.commit()
        conn.close()
        db.close()

        db = DB(storage)
        conn = db.open()
        new_sub = conn.root()['sub']

        x = new_sub.queryUtility(IFoo)
        assert_that(x, is_(MockSite))

        x = new_sub.queryUtility(IMock, 'foo')
        assert_that(x, is_(MockSite))


    def test_convert_with_utility_registered_on_class(self):
        comps = BLSM(None)

        comps.registerUtility(component=MockSite(),
                              provided=implementedBy(object))

        regs = list(comps.registeredUtilities())
        assert_that(regs, has_length(1))

        # But note that we can't actually look this up, regardless of whether
        # we use BTrees or not
        assert_that(regs[0], has_property('provided', implementedBy(object)))

        assert_that(calling(comps.getUtility).with_args(implementedBy(object)),
                    raises(ComponentLookupError))

    def test_convert_with_utility_no_provided(self):
        comps = BLSM(None)

        class AUtility(object):
            # Doesn't implement any interfaces
            pass

        # You can't easily register them this way anyway
        assert_that(calling(comps.registerUtility).with_args(AUtility()),
                    raises(TypeError, "The utility doesn't provide a single interface"))

    def test_convert_with_utility_dynamic_provided(self):
        comps = BLSM(None)
        comps.btree_threshold = 0
        class AUtility(object):
            # Doesn't implement any interfaces
            pass

        autility = AUtility()
        interface.alsoProvides(autility, IFoo)
        comps.registerUtility(autility)
        assert_that(comps._utility_registrations, is_(OOBTree))
        assert_that(comps._utility_registrations.keys(),
                    contains(
                        ((IFoo, '')),
                    ))
        assert_that(comps.utilities._provided, is_(OIBTree))
        assert_that(comps.utilities._adapters[0], is_(OOBTree))

        assert_that(comps.utilities._adapters[0][IFoo], is_(OOBTree))

    def test_convert_with_adapter_registered_on_class(self):
        comps = BLSM(None)

        comps.registerAdapter(
            _foo_factory,
            required=(object, type('str')),
            provided=IFoo)

        x = comps.getMultiAdapter((object(), 'str'), IFoo)
        assert_that(x, is_(1))

    def test_convert_mark_self_changed(self):
        comps = BLSM(None)

        comps.registerAdapter(
            _foo_factory,
            required=(object, type('str')),
            provided=IFoo)

        comps.registerAdapter(
            _foo_factory2,
            required=(object, type(0)),
            provided=IFoo)

        x = comps.getMultiAdapter((object(), 'str'), IFoo)
        assert_that(x, is_(1))


def _foo_factory(*_args):
    return 1
def _foo_factory2(*_args):
    return 2

class TestPermissiveOOBTree(unittest.TestCase):

    def test_default(self):
        # This is now legacy after BTrees 4.3.2, kept around for
        # ensuring it still works.
        from nti.site.site import _PermissiveOOBTree
        tree = _PermissiveOOBTree()
        key = object() # default comparison

        assert_that(tree.get(key), is_(none()))


from zope.interface.tests.test_adapter import CustomTypesBaseAdapterRegistryTests

class BTreeLocalAdapterRegistryCustomTypesTest(CustomTypesBaseAdapterRegistryTests):

    def _getMappingType(self):
        return OOBTree

    def _getProvidedType(self):
        return OIBTree

    def _getMutableListType(self):
        from persistent.list import PersistentList
        return PersistentList

    def _getLeafSequenceType(self):
        return self._getMutableListType()

    def _getBaseAdapterRegistry(self):
        return BTreeLocalAdapterRegistry

    def __bt_to_dict(self, bt):
        if not isinstance(bt, (OOBTree, OIBTree)):
            return bt

        return {
            k: self.__bt_to_dict(v)
            for k, v in bt.items()
        }

    def assertEqual(self, first, second, msg=None):
        # BTrees don't support equality tests like
        # dict and PersistentMapping do, so convert them to dicts.
        # They are also found at the top level of the
        # persistent maps, so those need converted too.
        from persistent.list import PersistentList
        if isinstance(first, (OOBTree, OIBTree)) and isinstance(second, (OOBTree, OIBTree)):
            self.assertEqual(type(first), type(second))
            first = self.__bt_to_dict(first)
            second = self.__bt_to_dict(second)
        elif isinstance(first, PersistentList) and isinstance(second, PersistentList):
            self.assertEqual(type(first), type(second))
            first = [self.__bt_to_dict(x) for x in first]
            second = [self.__bt_to_dict(x) for x in second]


        super().assertEqual(first, second, msg=msg)

    def test__addValueToLeaf_existing_is_tuple_TypeError(self):
        registry = self._makeOne()
        with self.assertRaisesRegex(TypeError, "Forbidding mutation"):
            registry._addValueToLeaf(('a',), 'b')
