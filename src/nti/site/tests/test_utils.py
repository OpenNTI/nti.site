#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from hamcrest import assert_that
from hamcrest import is_

from hamcrest import has_length


class TestUtils(unittest.TestCase):

    def test_event_unregister_warning(self):

        import warnings
        from ..utils import unregisterUtility
        from zope.component import getGlobalSiteManager
        from zope.interface import Interface
        class IFoo(Interface): # pylint:disable=inherit-non-class
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            gsm = getGlobalSiteManager()
            unregisterUtility(gsm, self, provided=IFoo, event=True)

            assert_that(w, has_length(1))
            assert_that(w[-1].category(), is_(FutureWarning))
