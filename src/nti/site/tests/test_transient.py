#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

import unittest

import pickle

from zope.component import globalSiteManager as BASE

from z3c.baseregistry.baseregistry import BaseComponents

from nti.site.transient import HostSiteManager as HSM
from nti.site.transient import TrivialSite

class TestHSM(unittest.TestCase):

    def _makeOne(self):
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))
        host_comps = BaseComponents(BASE, 'example.com', (BASE,))
        host_sm = HSM('example.com', 'siteman', host_comps, pers_comps)

        return host_sm, pers_comps, host_comps

    def test_cover(self):
        host_sm, pers_comps, host_comps = self._makeOne()

        assert_that(host_sm, has_property('host_components', is_(host_comps)))
        assert_that(host_sm, has_property('persistent_components', is_(pers_comps)))

    def test_pickle(self):
        host_sm = self._makeOne()[0]
        assert_that(calling(pickle.dumps).with_args(host_sm),
                    raises(TypeError, "BasedSiteManager should not be pickled"))

    def test_not_folderish(self):
        host_sm = self._makeOne()[0]
        assert_that(calling(host_sm.__setitem__).with_args('key', object()),
                    raises(AttributeError))


class TestTrivialSite(unittest.TestCase):

    def _makeOne(self):
        pers_comps = BaseComponents(BASE, 'persistent', (BASE,))
        host_comps = BaseComponents(BASE, 'example.com', (BASE,))
        host_sm = HSM('example.com', 'siteman', host_comps, pers_comps)

        site = TrivialSite(host_sm)
        return site, host_sm

    def test_no_pickle(self):
        site, _ = self._makeOne()
        assert_that(calling(pickle.dumps).with_args(site),
                    raises(TypeError, "TrivialSite should not be pickled"))

    def test_site_manager(self):
        site, sm = self._makeOne()
        assert_that(site.getSiteManager(), is_(sm))
