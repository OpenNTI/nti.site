#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import is_in

from nti.testing import base
from nti.testing.matchers import provides


from zope.interface.registry import UtilityRegistration
from zope.interface.interfaces import Registered

from zope.interface import Interface
from zope import interface

from zope.component.interfaces import ISite
from ..site import BTreeLocalSiteManager as LocalSiteManager
from zope.site import SiteManagerContainer
from zope.container.contained import Contained
from zope.location.interfaces import ILocationInfo

from ..localutility import install_utility_on_registration
from ..localutility import uninstall_utility_on_unregistration
from ..localutility import queryNextUtility

class TestInstallUninstall(base.AbstractTestBase):


    def test_install_uninstall(self):
        lsm = LocalSiteManager(None, None)
        registration = UtilityRegistration(lsm, None, None, None, None)
        event = Registered(registration)

        class IFoo(Interface):
            pass

        # If we're not contained, we get proxied!
        class Foo(Contained):
            pass

        install_utility_on_registration(Foo(), 'name', IFoo, event)

        assert_that(lsm['name'], is_(Foo))
        assert_that(lsm.getUtility(IFoo), is_(Foo))

        queryNextUtility(lsm['name'], IFoo)

        uninstall_utility_on_unregistration('name', IFoo, event)

        assert_that('name', is_not(is_in(lsm)))
        assert_that(lsm.queryUtility(IFoo), is_(none()))

class TestQueryNext(base.AbstractTestBase):

    def test_query(self):
        from zope.site import SiteManagerAdapter
        from zope import component
        component.provideAdapter(SiteManagerAdapter)
        top_site = SiteManagerContainer()
        top_sm = LocalSiteManager(top_site)
        top_site.setSiteManager(top_sm)
        assert_that(top_sm.__parent__, is_(top_site))
        assert_that(top_site, provides(ISite))
        interface.alsoProvides(top_site, ILocationInfo)

        child_site = SiteManagerContainer()
        child_site.__parent__ = top_site
        child_site.getParent = lambda: child_site.__parent__
        interface.alsoProvides(child_site, ILocationInfo)
        child_sm = LocalSiteManager(child_site)
        child_site.setSiteManager(child_sm)

        assert_that(child_sm.__bases__, is_((top_sm,)))


        class IFoo(Interface):
            pass

        @interface.implementer(IFoo)
        class Foo(Contained):
            pass

        child_foo = Foo()
        top_foo = Foo()

        child_foo.__parent__ = child_site
        top_foo.__parent__ = top_site

        top_sm.registerUtility(top_foo, IFoo)
        child_sm.registerUtility(child_foo, IFoo)

        child_foo.__conform__ = lambda self, _:  child_sm
        from zope import component
        component.getSiteManager(child_foo)


        x = queryNextUtility(child_foo, IFoo)
        assert_that(x, is_(top_foo))

        class IBaz(Interface): pass

        x = queryNextUtility(child_foo, IBaz)
        assert_that(x, is_(none()))

        x = queryNextUtility(top_foo, IFoo)
        assert_that(x, is_(none()))

        x = queryNextUtility(component.getGlobalSiteManager(), IFoo)
        assert_that(x, is_(none()))

        global_foo = Foo()
        component.provideUtility(global_foo, IFoo)
        x = queryNextUtility(component.getGlobalSiteManager(), IFoo)
        assert_that(x, is_(global_foo))
