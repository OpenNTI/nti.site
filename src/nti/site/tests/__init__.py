#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

logger = __import__('logging').getLogger(__name__)

import functools
import transaction

from zope import interface
from zope import component
from zope import lifecycleevent



from zope.component.hooks import setHooks
from zope.component.hooks import site as currentSite

from zope.component.interfaces import ISite

from ..site import BTreeLocalSiteManager
from zope.site import SiteManagerContainer

from zope.site.folder import Folder
from zope.site.folder import rootFolder

from zope.traversing.interfaces import IEtcNamespace

import ZODB

from ZODB.DemoStorage import DemoStorage

from nti.site.folder import HostSitesFolder

from nti.site.interfaces import IMainApplicationFolder


from nti.site.site import get_site_for_site_names

from nti.testing.layers import find_test
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin

import zope.testing.cleanup

current_mock_db = None
current_transaction = None

root_name = 'nti.dataserver'

def install_sites_folder(server_folder):
    sites = HostSitesFolder()
    str(sites) # coverage
    repr(sites) # coverage
    server_folder['++etc++hostsites'] = sites
    lsm = server_folder.getSiteManager()
    lsm.registerUtility(sites, provided=IEtcNamespace, name='hostsites')
    # synchronize_host_policies()

def install_main(conn):
    root = conn.root()

    # The root folder
    root_folder = rootFolder()
    conn.add(root_folder)  # Ensure we have a connection so we can become KeyRefs
    assert root_folder._p_jar is conn

    # The root is generally presumed to be an ISite, so make it so
    root_sm = BTreeLocalSiteManager(root_folder)  # site is IRoot, so __base__ is the GSM
    assert root_sm.__parent__ is root_folder
    assert root_sm.__bases__ == (component.getGlobalSiteManager(),)
    conn.add(root_sm)  # Ensure we have a connection so we can become KeyRefs
    assert root_sm._p_jar is conn

    root_folder.setSiteManager(root_sm)
    assert ISite.providedBy(root_folder)

    server_folder = Folder()
    interface.alsoProvides(server_folder, IMainApplicationFolder)
    conn.add(server_folder)
    root_folder['dataserver2'] = server_folder
    assert server_folder.__parent__ is root_folder
    assert server_folder.__name__ == 'dataserver2'
    assert root_folder['dataserver2'] is server_folder

    lsm = BTreeLocalSiteManager(server_folder)
    conn.add(lsm)
    assert lsm.__parent__ is server_folder
    assert lsm.__bases__ == (root_sm,)

    server_folder.setSiteManager(lsm)
    assert ISite.providedBy(server_folder)

    with currentSite(server_folder):
        assert component.getSiteManager() is lsm, "Component hooks must have been reset"

        root[root_name] = server_folder
        root['Application'] = root_folder  # The name that many Zope components assume

        lifecycleevent.added(root_folder)
        lifecycleevent.added(server_folder)

        install_sites_folder(server_folder)

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
