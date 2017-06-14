#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_


from nti.testing import base

import six
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
from ..runner import _tx_string

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
        c._root[u'nti.dataserver'] = TrivialSite(component.getGlobalSiteManager())
        with _site_cm(c, ('abc',)) as sitemanc:
            assert_that(sitemanc, is_(c._root[u'nti.dataserver']))

    def test_site_cm_not_installed(self):
        class MockConn(object):
            def __init__(self):
                self._root = {}
            def root(self):
                return self._root

        c = MockConn()
        c._root[u'nti.dataserver'] = TrivialSite(None)
        try:
            with _site_cm(c, ('abc',)):
                self.fail("Should not get here")
        except SiteNotInstalledError:
            pass

class TestRunner(base.AbstractTestBase):

    def setUp(self):
        super(TestRunner, self).setUp()
        db = ZODB.DB(DemoStorage(name='base'))
        component.provideUtility(db, IDatabase)

        conn = db.open()
        smc = conn.root()[u'nti.dataserver'] = SiteManagerContainer()
        smc.setSiteManager(component.getGlobalSiteManager())

        transaction.commit()
        conn.close()

    def test_run_description(self):
        expected_desc = None
        expected_desc_type = six.text_type

        # Note: This file's coding is utf-8!
        def func():
            "A docstring with utf-8 chars: 😀"
            assert_that(component.getSiteManager(), is_(component.getGlobalSiteManager()))
            assert_that(transaction.get().description, is_(expected_desc))
            assert_that(transaction.get().description, is_(expected_desc_type))

        expected_desc = _tx_string('func\n\n' + func.__doc__)
        run_job_in_site(func, site_names=('abc',))

        expected_desc = _tx_string('Test')
        run_job_in_site(func, job_name=b"Test")

        func.__name__ = '_'
        expected_desc = _tx_string(func.__doc__)
        run_job_in_site(func, site_names=('abc',))

        expected_desc = None
        run_job_in_site(lambda: None)

    def test_run_missing_name_doc(self):
        # Issue 16
        class Callable(object):
            # Like functools.partial, this doesn't expose a __name__ or __doc__.
            def __getattribute__(self, name):
                if name in ('__doc__', '__name__'):
                    raise AttributeError(name)
                return object.__getattrribute__(self, name)

            def __call__(self):
                assert_that(transaction.get().description, is_(''))


        run_job_in_site(Callable())
