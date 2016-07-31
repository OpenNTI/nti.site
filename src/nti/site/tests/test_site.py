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
does_not = is_not

import unittest

from zope import interface

from zope.interface import ro
from zope.interface import Interface

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
from nti.testing.matchers import is_true
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
import sys
PYPY = hasattr(sys, 'pypy_version_info')
from ZODB import DB
from ZODB.DemoStorage import DemoStorage

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


    def test_pickle_setstate_swap_class_zodb(self):
        storage = DemoStorage()
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

        import transaction
        transaction.commit()
        conn.close()
        db.close()

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

        # Now, we can register a couple adapters in the base, save everything,
        # and look it up in the sub (when the classes don't match)

        new_base.adapters.btree_provided_threshold = 0
        new_base.adapters.btree_map_threshold = 0
        # Note: this causes btree-ing the map to fail. The implementedBy callable has default comparison
        # and can't be stored in a btree. We handle that semi-gracefully now.
        # TODO: How about performance? Does this ever come up in real life?
        # Checking the data doesn't show that it does. (This part of the test could be
        # separated out)
        new_base.registerAdapter(_foo_factory,
                                 required=(object,),
                                 provided=IFoo)
        provided1 = new_base.adapters._provided
        new_base.registerAdapter(_foo_factory2,
                                 required=(IFoo,),
                                 provided=IMock)
        provided2 = new_base.adapters._provided
        assert_that(new_base._adapter_registrations, is_(BTrees.OOBTree.OOBTree))
        assert_that(new_base.adapters._provided, is_(BTrees.family64.OI.BTree))
        assert_that(new_base.adapters._adapters[0], is_({}))
        assert_that(new_base.adapters._adapters[1][IFoo], is_(BTrees.family64.OO.BTree))
        assert_that(provided1, is_(same_instance(provided2)))

        transaction.commit()
        conn.close()
        db.close()

        db = DB(storage)
        conn = db.open()
        new_sub = conn.root()['sub']

        x = new_sub.queryAdapter(self, IFoo)
        assert_that(x, is_(1))


        x = new_sub.queryAdapter(RootFoo(), IMock)
        assert_that(x, is_(2))

def _foo_factory(o):
    return 1
def _foo_factory2(o):
    return 2
