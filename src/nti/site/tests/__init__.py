#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

logger = __import__('logging').getLogger(__name__)

import functools
import transaction


from zope import component

from zope.component.hooks import setHooks
from zope.component.hooks import site as currentSite



from ..site import BTreeLocalSiteManager
from ..hostpolicy import install_main_application_and_sites
from zope.site import SiteManagerContainer

import ZODB

from ZODB.DemoStorage import DemoStorage

from ..site import get_site_for_site_names

from nti.testing.layers import find_test
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin

from hamcrest import assert_that
from nti.testing.matchers import provides
from ..interfaces import IMainApplicationFolder

import zope.testing.cleanup

current_mock_db = None
current_transaction = None

root_name = u'nti.dataserver'

def install_main(conn):
    def setup(f):
        assert_that(f, provides(IMainApplicationFolder))
    install_main_application_and_sites(conn,
                                       root_alias=root_name,
                                       main_name=u'dataserver2',
                                       main_setup=setup)

def init_db(db, conn=None):
    conn = db.open() if conn is None else conn
    global current_transaction
    if current_transaction != conn:
        current_transaction = conn
    install_main(conn)
    return conn

class mock_db_trans(object):

    def __init__(self, db=None, site_name=None):
        self.db = db or current_mock_db
        self._site_cm = None
        self._site_name = site_name

    def _check(self, conn):
        root = conn.root()
        if root_name not in root:
            install_main(conn)

    def __enter__(self):
        transaction.begin()
        self.conn = conn = self.db.open()
        global current_transaction
        current_transaction = conn
        self._check(conn)

        sitemanc = conn.root()[root_name]
        if self._site_name:
            with currentSite(sitemanc):
                sitemanc = get_site_for_site_names((self._site_name,))

        self._site_cm = currentSite(sitemanc)
        self._site_cm.__enter__()
        assert component.getSiteManager() == sitemanc.getSiteManager()
        return conn

    def __exit__(self, t, v, tb):
        result = self._site_cm.__exit__(t, v, tb)
        global current_transaction
        body_raised = t is not None
        try:
            try:
                if not transaction.isDoomed():
                    transaction.commit()
                else:
                    transaction.abort()
            except Exception:
                transaction.abort()
                raise
            finally:
                current_transaction = None
                self.conn.close()
        except Exception:
            if not body_raised:
                raise
            logger.exception("Failed to cleanup trans, but body raised exception too")
        reset_db_caches(self.db)
        return result

def reset_db_caches(db=None):
    if db is not None:
        db.pool.map(lambda conn: conn.cacheMinimize())

def _mock_ds_wrapper_for(func, db, teardown=None):

    @functools.wraps(func)
    def f(*args):
        global current_mock_db
        current_mock_db = db
        init_db(db)

        sitemanc = SiteManagerContainer()
        sitemanc.setSiteManager(BTreeLocalSiteManager(None))

        with currentSite(sitemanc):
            assert component.getSiteManager() == sitemanc.getSiteManager()
            try:
                func(*args)
            finally:
                current_mock_db = None
                if teardown:
                    teardown()

    return f

def WithMockDS(*args, **kwargs):
    teardown = lambda: None
    db = ZODB.DB(DemoStorage(name='Users'))
    if len(args) == 1 and not kwargs:
        # Being used as a plain decorator
        func = args[0]
        return _mock_ds_wrapper_for(func, db, teardown)
    return lambda func: _mock_ds_wrapper_for(func, db , teardown)


class SharedConfiguringTestLayer(ZopeComponentLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin):

    set_up_packages = ('nti.site',)

    @classmethod
    def db(cls):
        return current_mock_db

    @classmethod
    def setUp(cls):
        setHooks()
        cls.setUpPackages()
        # Force all the thresholds low so that we do as much testing as possible
        # with btrees.
        from ..site import BTreeLocalAdapterRegistry
        from ..folder import HostPolicySiteManager
        assert hasattr(HostPolicySiteManager, 'btree_threshold')
        HostPolicySiteManager.btree_threshold = 0
        assert hasattr(BTreeLocalAdapterRegistry, 'btree_provided_threshold')
        assert hasattr(BTreeLocalAdapterRegistry, 'btree_map_threshold')
        cls._orig_provided = BTreeLocalAdapterRegistry.btree_provided_threshold
        cls._orig_map = BTreeLocalAdapterRegistry.btree_map_threshold
        BTreeLocalAdapterRegistry.btree_provided_threshold = 0
        BTreeLocalAdapterRegistry.btree_map_threshold = 0

    @classmethod
    def tearDown(cls):
        from ..site import BTreeLocalAdapterRegistry
        from ..folder import HostPolicySiteManager
        del HostPolicySiteManager.btree_threshold
        assert hasattr(HostPolicySiteManager, 'btree_threshold')
        BTreeLocalAdapterRegistry.btree_provided_threshold = cls._orig_provided
        BTreeLocalAdapterRegistry.btree_map_threshold = cls._orig_map
        cls.tearDownPackages()
        zope.testing.cleanup.cleanUp()

    @classmethod
    def testSetUp(cls, test=None):
        setHooks()
        test = test or find_test()
        test.db = cls.db()

    @classmethod
    def testTearDown(cls):
        pass

import unittest

class SiteTestCase(unittest.TestCase):
    layer = SharedConfiguringTestLayer
