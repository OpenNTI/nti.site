#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import contains
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import none
from hamcrest import has_length
does_not = is_not

import unittest

from zope import interface

from zope.interface import ro
from zope.interface import implementedBy
from zope.interface import Interface
from zope.interface.interfaces import ComponentLookupError

from zope.component.hooks import getSite
from zope.component.hooks import setSite
from zope.component.hooks import site as currentSite

from zope.location.interfaces import LocationError

from zope.component import globalSiteManager as BASE

from z3c.baseregistry.baseregistry import BaseComponents

from nti.site.interfaces import IHostPolicyFolder
from nti.site.subscribers import threadSiteSubscriber
from nti.site.transient import HostSiteManager as HSM
from ..transient import TrivialSite
from ..site import get_site_for_site_names
from ..site import find_site_components
from ..site import get_component_hierarchy
from ..site import get_component_hierarchy_names

from nti.site.tests import SharedConfiguringTestLayer

from nti.testing.matchers import validly_provides
from nti.testing.matchers import is_false
from nti.testing.base import AbstractTestBase

from persistent import Persistent

import fudge

class IMock(Interface):
    pass

@interface.implementer(IMock)
class MockSite(object):

    __name__ = None
    __parent__ = None

    def __init__(self, site_man=None):
        self.site_man = site_man

    def getSiteManager(self):
        return self.site_man

class IFoo(Interface):
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

            # ... we fail...
            assert_that(calling(threadSiteSubscriber).with_args(new_site2, None),
                        raises(LocationError))

            # ...unless they are both HostPolicyFolders...
            interface.alsoProvides(new_site, IHostPolicyFolder)
            interface.alsoProvides(new_site2, IHostPolicyFolder)
            threadSiteSubscriber(new_site2, None)

            # ... which does not change the site
            assert_that(getSite(), is_(same_instance(new_site)))

class TestGetSiteForSiteNames(AbstractTestBase):

    @fudge.patch('nti.site.site.find_site_components')
    def test_no_persistent_site(self, fake_find):
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))
        host_comps = BaseComponents(BASE, 'example.com', (BASE,))
        host_sm = HSM('example.com', 'siteman', host_comps, pers_comps)
        class PersistentTrivialSite(Persistent, TrivialSite):
            pass
        trivial_site = PersistentTrivialSite(host_sm)
        fake_find.is_callable().returns(pers_comps)


        x = get_site_for_site_names(('',), trivial_site)

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

        class MockSite(object):
            __parent__ = None
            __name__ = None

            def __init__(self):
                self.__parent__ = {}

        site_comps_1 = BaseComponents(pers_comps, '1', (pers_comps,))
        site_comps_2 = BaseComponents(site_comps_1, '2', (site_comps_1,))

        site = MockSite()
        site.__parent__[site_comps_1.__name__] = site_comps_1
        site.__parent__[site_comps_2.__name__] = site_comps_2

        fake_find.is_callable().returns(site_comps_2)

        x = list(get_component_hierarchy(site))
        assert_that(x, is_([site_comps_2, site_comps_1]))

        x = list(get_component_hierarchy_names(site))
        assert_that(x, is_(['2', '1']))

        x = list(get_component_hierarchy_names(site, reverse=True))
        assert_that(x, is_(['1', '2']))

from ..site import BTreeLocalSiteManager as BLSM
from ..site import _LocalAdapterRegistry
from ..site import BTreeLocalAdapterRegistry
from ..site import WrongRegistrationTypeError

from ZODB import DB
from ZODB.DemoStorage import DemoStorage
import transaction

import pickle
try:
    import zodbpickle.fastpickle as zpickle
except ImportError:
    import zodbpickle.pickle as zpickle # pypy
import BTrees.OOBTree

class TestBTreeSiteMan(AbstractTestBase):


    def test_pickle_setstate_swap_class(self):
        base_comps = BLSM(None)
        # replace with "broken"
        base_comps.adapters = _LocalAdapterRegistry()
        base_comps.utilities = _LocalAdapterRegistry()

        sub_comps = BLSM(None)
        sub_comps.__bases__ = (base_comps,)

        assert_that(sub_comps.adapters.__bases__, is_((base_comps.adapters,)))
        assert_that(sub_comps.utilities.__bases__, is_((base_comps.utilities,)))

        for p in pickle, zpickle:
            new_base, new_sub = p.loads(p.dumps([base_comps, sub_comps]))

            # Still in place
            assert_that(new_sub.adapters.__bases__, is_((new_base.adapters,)))
            assert_that(new_sub.utilities.__bases__, is_((new_base.utilities,)))

            # And they changed type
            assert_that(new_sub.adapters.__bases__[0], is_(BTreeLocalAdapterRegistry))
            assert_that(new_sub.utilities.__bases__[0], is_(BTreeLocalAdapterRegistry))


    def _store_base_subs_in_zodb(self, storage):
        db = DB(storage)
        conn = db.open()

        base_comps = BLSM(None)
        base_comps.btree_threshold = 0
        base_comps.__name__ = u'base'
        # replace with "broken"
        base_comps.adapters = _LocalAdapterRegistry()
        base_comps.utilities = _LocalAdapterRegistry()

        sub_comps = BLSM(None)
        sub_comps.__name__ = u'sub'
        sub_comps.__bases__ = (base_comps,)

        assert_that(sub_comps.adapters.__bases__, is_((base_comps.adapters,)))
        assert_that(sub_comps.utilities.__bases__, is_((base_comps.utilities,)))
        assert_that(sub_comps.utilities.__bases__[0], is_(_LocalAdapterRegistry))

        conn.root()['base'] = base_comps
        conn.root()['sub'] = sub_comps


        transaction.commit()
        conn.close()
        db.close()

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


        new_base.adapters.btree_provided_threshold = 0
        new_base.adapters.btree_map_threshold = 1
        # Note: this used-to cause btree-ing the map to fail. The
        # implementedBy callable previously had default comparison and can't be
        # stored in a btree. As of zope.interface 4.3.0, this is fixed.

        new_base.registerAdapter(_foo_factory,
                                 required=(object,),
                                 provided=IFoo)

        new_base.registerAdapter(_foo_factory2,
                                 required=(IFoo,),
                                 provided=IMock)

        assert_that(new_base._adapter_registrations, is_(BTrees.OOBTree.OOBTree))
        assert_that(new_base._adapter_registrations.keys(),
                    contains(
                        ((IFoo,), IMock, u''),
                        ((implementedBy(object),), IFoo, u'' ),
                    ))
        assert_that(new_base.adapters._provided, is_(BTrees.family64.OI.BTree))
        assert_that(new_base.adapters._adapters[0], is_({}))

        assert_that(new_base.adapters._adapters[1][IFoo], is_(dict))


        new_base.registerAdapter(_foo_factory2,
                                 required=(IFoo,),
                                 provided=IFoo)

        assert_that(new_base.adapters._adapters[1][IFoo], is_(BTrees.family64.OO.BTree))

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


        new_base.utilities.btree_provided_threshold = 0
        new_base.utilities.btree_map_threshold = 0

        new_base.registerUtility(MockSite(),
                                 provided=IFoo)
        provided1 = new_base.adapters._provided
        # In the past, we couldn't register by implemented, but now we can.
        new_base.registerUtility(MockSite(),
                                 provided=implementedBy(MockSite),
                                 name=u'foo')

        provided2 = new_base.adapters._provided
        # Make sure that it only converted once
        assert_that(provided1, is_(same_instance(provided2)))
        assert_that(new_base._utility_registrations, is_(BTrees.OOBTree.OOBTree))

        assert_that(new_base._utility_registrations.keys(),
                    contains(
                        (IFoo, u''),
                        ((implementedBy(MockSite), u'foo')),
                    ))
        assert_that(new_base.utilities._provided, is_(BTrees.family64.OI.BTree))
        assert_that(new_base.utilities._adapters[0], is_(BTrees.family64.OO.BTree))

        assert_that(new_base.utilities._adapters[0][IFoo], is_(BTrees.family64.OO.BTree))


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
        x = new_sub.queryUtility(MockSite, u'foo')
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


        new_base.utilities.btree_provided_threshold = 0
        new_base.utilities.btree_map_threshold = 0

        new_base.registerUtility(MockSite(),
                                 provided=IFoo)
        provided1 = new_base.adapters._provided
        # Previously this would fail. Now it works.
        new_base.registerUtility(MockSite(),
                                 provided=implementedBy(object),
                                 name=u'foo')

        new_base.registerUtility(MockSite(),
                                 provided=IMock,
                                 name=u'foo')

        provided2 = new_base.adapters._provided
        # Make sure that it only converted once
        assert_that(provided1, is_(same_instance(provided2)))
        assert_that(new_base._utility_registrations, is_(BTrees.OOBTree.OOBTree))

        assert_that(new_base._utility_registrations.keys(),
                    contains(
                        (IFoo, u''),
                        (IMock, u'foo'),
                        (implementedBy(object), u'foo'),
                    ))
        assert_that(new_base.utilities._provided, is_(BTrees.family64.OI.BTree))
        assert_that(new_base.utilities._adapters[0], is_(BTrees.family64.OO.BTree))

        assert_that(new_base.utilities._adapters[0][IFoo], is_(BTrees.family64.OO.BTree))


        transaction.commit()
        conn.close()
        db.close()

        db = DB(storage)
        conn = db.open()
        new_sub = conn.root()['sub']

        x = new_sub.queryUtility(IFoo)
        assert_that(x, is_(MockSite))

        x = new_sub.queryUtility(IMock, u'foo')
        assert_that(x, is_(MockSite))


    def test_convert_with_utility_registered_on_class(self):
        comps = BLSM(None)

        comps.utilities.btree_provided_threshold = 0
        comps.utilities.btree_map_threshold = 0

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

        comps.utilities.btree_provided_threshold = 0
        comps.utilities.btree_map_threshold = 0

        class AUtility(object):
            # Doesn't implement any interfaces
            pass

        # You can't easily register them this way anyway
        assert_that(calling(comps.registerUtility).with_args(AUtility()),
                    raises(TypeError, "The utility doesn't provide a single interface"))

    def test_convert_with_utility_dynamic_provided(self):
        comps = BLSM(None)

        comps.btree_threshold = 0
        comps.utilities.btree_provided_threshold = 0
        comps.utilities.btree_map_threshold = 0

        class AUtility(object):
            # Doesn't implement any interfaces
            pass

        autility = AUtility()
        interface.alsoProvides(autility, IFoo)
        comps.registerUtility(autility)
        assert_that(comps._utility_registrations, is_(BTrees.OOBTree.OOBTree))
        assert_that(comps._utility_registrations.keys(),
                    contains(
                        ((IFoo, u'')),
                    ))
        assert_that(comps.utilities._provided, is_(BTrees.family64.OI.BTree))
        assert_that(comps.utilities._adapters[0], is_(BTrees.family64.OO.BTree))

        assert_that(comps.utilities._adapters[0][IFoo], is_(BTrees.family64.OO.BTree))

    def test_convert_with_adapter_registered_on_class(self):
        comps = BLSM(None)

        comps.btree_threshold = 0
        comps.adapters.btree_provided_threshold = 0
        comps.utilities.btree_map_threshold = 0

        comps.registerAdapter(
                           _foo_factory,
                           required=(object, type('str')),
                           provided=IFoo)

        x = comps.getMultiAdapter((object(), 'str'), IFoo)
        assert_that(x, is_(1))


def _foo_factory(*args):
    return 1
def _foo_factory2(*args):
    return 2

class TestPermissiveOOBTree(unittest.TestCase):

    def test_default(self):
        # This is now legacy after BTrees 4.3.2, kept around for
        # ensuring it still works.
        from nti.site.site import _PermissiveOOBTree
        tree = _PermissiveOOBTree()
        key = object() # default comparison

        assert_that(tree.get(key), is_(none()))
