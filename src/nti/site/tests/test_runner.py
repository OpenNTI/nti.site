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


from hamcrest import assert_that
from hamcrest import is_


from nti.testing import base

import transaction

from zope import component
from ZODB.interfaces import IDatabase
from ZODB.Connection import Connection
import ZODB.DB
from ZODB.DemoStorage import DemoStorage
from zope.site import SiteManagerContainer

from ..runner import _connection_cm
from ..runner import _site_cm
from ..runner import run_job_in_site

from ..transient import TrivialSite

from ..interfaces import SiteNotInstalledError



class TestConnectionCM(base.AbstractTestBase):

    def test_connection_cm(self):
        db = ZODB.DB(DemoStorage(name='base'))
        component.provideUtility(db, IDatabase)

        with _connection_cm() as c:
            assert_that(c, is_(Connection))

class TestSiteCM(base.AbstractTestBase):

    def test_site_cm(self):
        class MockConn(object):
            def __init__(self):
                self._root = {}
            def root(self):
                return self._root

        c = MockConn()
        c._root['nti.dataserver'] = TrivialSite(component.getGlobalSiteManager())
        with _site_cm(c, ('abc',)) as sitemanc:
            assert_that(sitemanc, is_(c._root['nti.dataserver']))

    def test_site_cm_not_installed(self):
        class MockConn(object):
            def __init__(self):
                self._root = {}
            def root(self):
                return self._root

        c = MockConn()
        c._root['nti.dataserver'] = TrivialSite(None)
        try:
            with _site_cm(c, ('abc',)):
                self.fail("Should not get here")
        except SiteNotInstalledError:
            pass

class TestRunner(base.AbstractTestBase):

    def test_run(self):
        db = ZODB.DB(DemoStorage(name='base'))
        component.provideUtility(db, IDatabase)

        conn = db.open()
        smc = conn.root()['nti.dataserver'] = SiteManagerContainer()
        smc.setSiteManager(component.getGlobalSiteManager())

        transaction.commit()
        conn.close()

        def func():
            "A docstring"
            assert_that(component.getSiteManager(), is_(component.getGlobalSiteManager()))

        run_job_in_site(func, site_names=('abc',))

        run_job_in_site(func, job_name="Test")

        run_job_in_site(lambda: None)
