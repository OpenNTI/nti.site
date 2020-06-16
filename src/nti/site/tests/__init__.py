#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

import unittest
import functools

import transaction

from ZODB.DemoStorage import DemoStorage
from hamcrest import assert_that

from nti.testing import zodb
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import find_test
from nti.testing.matchers import provides

from zope import component
from zope.component.hooks import setHooks
from zope.component.hooks import site as currentSite
from zope.site import SiteManagerContainer
import ZODB
import zope.testing.cleanup


from ..hostpolicy import install_main_application_and_sites
from ..interfaces import IMainApplicationFolder
from ..site import BTreeLocalSiteManager
from ..site import get_site_for_site_names


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
    install_main(conn)
    return conn

class current_db_site_trans(zodb.mock_db_trans):

    def __init__(self, db=None, site_name=None):
        super(current_db_site_trans, self).__init__(db)
        self._site_cm = None
        self._site_name = site_name

    def on_connection_opened(self, conn):
        super(current_db_site_trans, self).on_connection_opened(conn)

        root = conn.root()
        if root_name not in root:
            install_main(conn)

        sitemanc = conn.root()[root_name]
        if self._site_name:
            with currentSite(sitemanc):
                sitemanc = get_site_for_site_names((self._site_name,))

        self._site_cm = currentSite(sitemanc)
        self._site_cm.__enter__() # pylint:disable=no-member
        assert component.getSiteManager() == sitemanc.getSiteManager()
        return conn

    def __exit__(self, t, v, tb):
        result = self._site_cm.__exit__(t, v, tb) # pylint:disable=no-member
        super(current_db_site_trans, self).__exit__(t, v, tb)
        return result


mock_db_trans = current_db_site_trans # BWC, remove in 2021
reset_db_caches = zodb.reset_db_caches # BWC, remove in 2021

def _mock_ds_wrapper_for(func, db):

    @functools.wraps(func)
    def f(*args):
        old_db = zodb.ZODBLayer.db
        try:
            zodb.ZODBLayer.db = db
            if SharedConfiguringTestLayer.current_test is not None:
                SharedConfiguringTestLayer.current_test.db = db
            # We created the DB fresh, so we know we will have to
            # open a transaction to be able to set it up.
            transaction.begin()
            init_db(db)
            transaction.commit()

            sitemanc = SiteManagerContainer()
            sitemanc.setSiteManager(BTreeLocalSiteManager(None))

            with currentSite(sitemanc):
                assert component.getSiteManager() == sitemanc.getSiteManager()
                func(*args)
        finally:
            db.close()
            zodb.ZODBLayer.db = old_db
    return f

def WithMockDS(*args, **kwargs):
    db = ZODB.DB(DemoStorage(name='Users'))
    if len(args) == 1 and not kwargs:
        # Being used as a plain decorator
        func = args[0]
        return _mock_ds_wrapper_for(func, db)
    return lambda func: _mock_ds_wrapper_for(func, db)


class SharedConfiguringTestLayer(zodb.ZODBLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin):

    set_up_packages = ('nti.site',)

    current_test = None

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
    def testSetUp(cls, test=None): # pylint:disable=arguments-differ
        setHooks()
        cls.current_test = test = test or find_test()
        test.db = cls.db

    @classmethod
    def testTearDown(cls):
        cls.current_test.db = None
        cls.current_test = None



class SiteTestCase(unittest.TestCase):
    layer = SharedConfiguringTestLayer
