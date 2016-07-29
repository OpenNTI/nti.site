#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from hamcrest import raises
from hamcrest import calling
from hamcrest import assert_that
does_not = is_not

from nti.testing.base import AbstractTestBase
import fudge

from zope.interface import implementer

from zope.component import globalSiteManager as BASE
from zope.component.hooks import getSite

from z3c.baseregistry.baseregistry import BaseComponents

from nti.site.transient import HostSiteManager as HSM
from nti.site.transient import TrivialSite

from zope.site.interfaces import IRootFolder
from ..interfaces import IMainApplicationFolder

from ..subscribers import threadSiteSubscriber

class TestSubscriber(AbstractTestBase):

    def test_root_folder_not_set(self):
        @implementer(IRootFolder)
        class Root(object):
            pass

        threadSiteSubscriber(Root(), None)

        assert_that(getSite(), is_(none()))

    def test_main_folder_not_set(self):
        @implementer(IMainApplicationFolder)
        class Main(object):
            pass

        threadSiteSubscriber(Main(), None)

        assert_that(getSite(), is_(none()))

    @fudge.patch('nti.site.subscribers.getSite')
    def test_not_replace_same(self, fake_get):
        fake_get.is_callable().returns(self)

        # If we actually tried to set TestSubscriber as the site,
        # we'd blow up
        threadSiteSubscriber(self, None)

    @fudge.patch('nti.site.subscribers.getSite')
    def test_returns_unsettable_proxy(self, fake_get):
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))
        host_comps = BaseComponents(BASE, 'example.com', (BASE,))
        host_sm = HSM('example.com', 'siteman', host_comps, pers_comps)

        fake_get.is_callable().returns(TrivialSite(host_sm))

        host_comps2 = BaseComponents(BASE, 'other.com', (BASE,))
        host_sm2 = HSM('other.com', 'siteman', host_comps2, pers_comps)

        threadSiteSubscriber(TrivialSite(host_sm2), None)

        # Existing host comps are preserved
        assert_that(getSite().getSiteManager().host_components, is_(host_comps))

        # and it's proxied and we can't change it
        assert_that(calling(getSite().setSiteManager).with_args(None),
                    raises(ValueError, "Cannot set site manager on proxy"))
