#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import assert_that
from hamcrest import same_instance
does_not = is_not

import fudge

from zope.interface import implementer

from zope.component import globalSiteManager as BASE

from zope.component.hooks import getSite
from zope.component.hooks import setSite

from zope.site.site import LocalSiteManager as LSM

from z3c.baseregistry.baseregistry import BaseComponents

from zope.site.interfaces import IRootFolder

from nti.site.interfaces import IMainApplicationFolder

from nti.site.subscribers import threadSiteSubscriber

from nti.site.transient import HostSiteManager as HSM
from nti.site.transient import TrivialSite

from nti.testing.base import AbstractTestBase


class TestSubscriber(AbstractTestBase):

    def _check_site(self, new_site, expected_after_subscriber):
        threadSiteSubscriber(new_site, None)
        assert_that(getSite(), expected_after_subscriber)

    def test_root_folder_not_set_if_site_installed(self):
        installed = TrivialSite(LSM(None))
        setSite(installed)

        @implementer(IRootFolder)
        class Root(object):
            pass

        self._check_site(Root(), is_(same_instance(installed)))

    def test_main_folder_not_set_if_site_installed(self):
        installed = TrivialSite(LSM(None))
        setSite(installed)

        @implementer(IMainApplicationFolder)
        class Main(object):
            pass

        self._check_site(Main(), is_(same_instance(installed)))

    def test_root_folder_set_if_no_site_installed(self):
        @implementer(IRootFolder)
        class Root(object):
            def getSiteManager(self):
                return LSM(None)

        self._check_site(Root(), is_(Root))

    def test_main_folder_set_if_no_site_installed(self):
        @implementer(IMainApplicationFolder)
        class Main(object):
            def getSiteManager(self):
                return LSM(None)

        self._check_site(Main(), is_(Main))

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
