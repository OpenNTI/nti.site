#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for testing code that uses :mod:`nti.site`.

Most of the functionality exposed through this module uses :mod:`ZODB`
to test persistence and transaction handling and is based on the
support code from :mod:`nti.testing.zodb`.

.. versionadded:: 2.1.0
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


import unittest
import functools

from ZODB.DemoStorage import DemoStorage
from hamcrest import assert_that

from nti.testing import zodb
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import find_test
from nti.testing.matchers import provides

from zope import component
from zope.component.hooks import setHooks
from zope.component.hooks import resetHooks
from zope.component.hooks import site as currentSite
from zope.site import SiteManagerContainer
import ZODB
import zope.testing.cleanup

from .hostpolicy import install_main_application_and_sites
from . import hostpolicy
from .interfaces import IMainApplicationFolder
from .site import BTreeLocalSiteManager
from .site import get_site_for_site_names

__all__ = [
    'setHooks',
    'resetHooks',
    'print_tree',
    'persistent_site_trans',
    'SharedConfiguringTestLayer',
    'SiteTestCase',
    'uses_independent_db_site',
]

def format_tree(folder, **kwargs):
    """
    Like :func:`print_tree`, but returns the results as a string
    instead of printing them to ``stdout`` or a file.

    Any *file* argument given is ignored.

    .. versionadded:: 2.2.0
    """
    if str is bytes:
        # Handles unicode and bytes mixed appropriately
        import cStringIO as io
    else:
        import io
    out = io.StringIO()
    kwargs['file'] = out
    print_tree(folder, **kwargs)
    return out.getvalue()


def print_tree(folder, **kwargs):
    """
    print_tree(folder, file=sys.stdout, show_unknown=repr, basic_indent='    ', details=('id', 'type', 'len', 'siteManager')) -> None

    Print a descriptive tree of the contents of the dict-like *folder* to *file*.

    Pass a subset of *details* to disable printing certain information
    when it isn't relavent.

    .. versionchanged:: 2.2.0
       Add several arguments including *show_unknown*, *details*.
       Print the contents of site managers by default.
       Fix a bug not passing the *basic_indent* to recursive calls.
    """
    # pylint:disable=too-many-locals,too-many-branches,too-many-statements
    # XXX: Refactor me.
    import sys
    from zope.site.interfaces import IRootFolder
    from zope.component.interfaces import ISite

    file = kwargs.get('file', sys.stdout)
    seen = kwargs.get('seen')
    if seen is None:
        seen = kwargs['seen'] = dict()
    basic_indent = kwargs.get('basic_indent', '    ')
    depth = kwargs.get('depth', 1)
    details = kwargs.get('details', ('id', 'type', 'len', 'siteManager'))
    name = kwargs.get('name', None)
    show_unknown = kwargs.get('show_unknown', repr)
    known_types = kwargs.get('known_types', (int, str, type(u''), float, type(None)))
    extra_details = kwargs.get('extra_details', lambda o: ())

    indent = basic_indent * depth
    folder_id = id(folder)

    if name is None:
        name = getattr(folder, '__name__', None)
        if not name:
            if getattr(folder, '_p_jar', None) and folder._p_jar.root() is folder:
                name = "<Connection Root Dictionary>"
            else:
                name = str(folder)

    if folder_id in seen:
        print(indent, name, '->', seen[folder_id], file=file)
        return
    seen[folder_id] = name + ' ' + str(folder_id)

    provs = []
    for iface in ISite, IRootFolder, IMainApplicationFolder:
        if iface.providedBy(folder):
            provs.append(iface.__name__)
    if provs:
        name = '<' + ','.join(provs) + '>: ' + name

    print_args = []
    if indent:
        print_args.append(indent)
    print_args.append(name)
    if 'id' in details:
        print_args.append(folder_id)
    if 'len' in details:
        try:
            print_args.append('len=' + str(len(folder)))
        except TypeError:
            pass
    if 'type' in details:
        print_args.append(type(folder))

    print_args.extend(extra_details(folder))

    if not hasattr(folder, 'items'):
        print_args.append('=>')
        if isinstance(folder, known_types):
            print_args.append(repr(folder))
        else:
            print_args.append(show_unknown(folder))

    print(*print_args, file=file)

    if hasattr(folder, 'items'):
        recur_args = kwargs.copy()
        recur_args['depth'] = depth + 1
        for k, v in sorted(folder.items()):
            recur_args['name'] = k
            print_tree(v, **recur_args)

    if 'siteManager' in details and ISite.providedBy(folder):
        site_man = folder.getSiteManager()
        recur_args = kwargs.copy()
        recur_args['depth'] = depth + 1
        recur_args['name'] = '<Site Manager> name=' + site_man.__name__
        print_tree(site_man, **recur_args)


class persistent_site_trans(zodb.mock_db_trans):
    """
    Context manager for a ZODB database connection and
    active ``zope.component`` site (usually) persisted in the database.

    .. versionchanged:: 2.1.0
       While there was no previous public version of this class,
       there was a private version in ``nti.site.tests``. That version
       called :func:`.install_main_application_and_sites` setting
       the *root_alias* to the :attr:`main_application_folder_name`.
       Since older versions of that function installed the *root_alias* to point
       to the *main_name*, this used result in no alias for the root folder in the
       root. Now, there will be an alias (at :obj:`~.DEFAULT_ROOT_ALIAS`).
    """

    #: The site to make active by default and when looking up
    #: a *site_name*. This must identify an object in the root
    #: of the database that provides :class:`~.IMainApplicationFolder`.
    main_application_folder_name = hostpolicy.DEFAULT_MAIN_ALIAS

    def __init__(self, db=None, site_name=None):
        """
        :param db: See :class:`nti.testing.zodb.mock_db_trans`
        :keyword str site_name: The name of a site to be made current
            during execution of the body.
            The site is found using :func:`~.get_site_for_site_names`
            while :attr:`main_application_folder_name` is the current site.
            If not given, the site found at :attr:`main_application_folder_name`
            will be the current site.
        """
        super(persistent_site_trans, self).__init__(db)
        self._site_cm = None
        self._site_name = site_name

    def on_application_and_sites_installed(self, folder):
        """
        Called when the main application and sites have been installed. This
        may not be called every time an instance of this class is used, as
        the database may be persistent.
        """
        assert_that(folder, provides(IMainApplicationFolder))

    def on_main_application_folder_missing(self, conn):
        """
        Called from :meth:`on_connection_opened` when the :attr:`main_application_folder_name`
        is not found in the root of the *conn*.

        This method calls :func:`~.install_main_application_and_sites`, passing
        :attr:`main_application_folder_name` as the *main_alias*.
        """
        install_main_application_and_sites(conn,
                                           main_alias=self.main_application_folder_name,
                                           main_setup=self.on_application_and_sites_installed)

    def on_connection_opened(self, conn):
        super(persistent_site_trans, self).on_connection_opened(conn)
        main_name = hostpolicy.text_type(self.main_application_folder_name)

        root = conn.root()
        if main_name not in root:
            self.on_main_application_folder_missing(conn)

        sitemanc = conn.root()[hostpolicy.text_type(self.main_application_folder_name)]
        if self._site_name:
            with currentSite(sitemanc):
                sitemanc = get_site_for_site_names((self._site_name,))

        self._site_cm = currentSite(sitemanc)
        self._site_cm.__enter__() # pylint:disable=no-member
        assert component.getSiteManager() == sitemanc.getSiteManager()
        return conn

    def __exit__(self, t, v, tb):
        result = self._site_cm.__exit__(t, v, tb) # pylint:disable=no-member
        super(persistent_site_trans, self).__exit__(t, v, tb)
        return result


mock_db_trans = persistent_site_trans # BWC, remove in 2021
reset_db_caches = zodb.reset_db_caches # BWC, remove in 2021

def _mock_ds_wrapper_for(func, installer_factory, installer_kwargs, db_factory,
                         marker=object()):

    @functools.wraps(func)
    def f(*args):
        # we may not be in a layer that's done this. Note that we don't tear it down though.
        # This is needed to run ``install_main_application_and_sites``
        setHooks()
        db = db_factory()

        old_db = zodb.ZODBLayer.db
        old_func_db = marker
        try:
            zodb.ZODBLayer.db = db
            if SharedConfiguringTestLayer.current_test is not None:
                SharedConfiguringTestLayer.current_test.db = db
            if args and isinstance(args[0], unittest.TestCase):
                # self
                old_func_db = getattr(args[0], 'db', marker)
                args[0].db = db

            with installer_factory(db, **installer_kwargs):
                pass

            sitemanc = SiteManagerContainer()
            sitemanc.setSiteManager(BTreeLocalSiteManager(None))

            with currentSite(sitemanc):
                assert component.getSiteManager() == sitemanc.getSiteManager()
                func(*args)
        finally:
            if args and isinstance(args[0], unittest.TestCase):
                if old_func_db is marker:
                    del args[0].db
                else:
                    args[0].db = old_func_db
            db.close()
            zodb.ZODBLayer.db = old_db
    return f


def default_db_factory():
    return ZODB.DB(DemoStorage(name='Users'))

def uses_independent_db_site(*args, **kwargs):
    """
    uses_independent_db_site(db_factory=None, installer_factory=persistent_site_trans, installer_kwargs={}) -> function

    A decorator or decorator factory. Creates a new database using *db_factory*,
    initializes it using *installer_factory*, and then runs the body of the function
    in a site and site manager that are disconnected from the database.

    If the function is a unittest method, the unittest object's ``db`` attribute
    will be set to the created db during executing. Likewise, the :class:`nti.testing.zodb.ZODBLayer`
    ``db`` attribute (and layers that extend from it like :class:`SharedConfiguringTestLayer`)
    will be set to this object and returned to the previous value on exit.

    This can be called as given in the signature, or can be called with no arguments::

        class MyTest(TestCase):

            @uses_independent_db_site
            def test_something(self):
                pass

            @uses_independent_db_site(installer_factory=MyCustomFactory)
            def test_something_else(self):
                pass

    The body of the function is free to use :class:`persistent_site_trans` statements.
    They will default to using the database established here instead of
    a database established by a test layer (which should be the same in most cases).

    :keyword callable db_factory: The 0-argument factory used to create a DB to pass
       to the installer.

    :keyword type installer_factory: The factory used to create
       the installer. The installer executes before the body of the wrapped
       function. This defaults to :class:`persistent_site_trans`, but can be
       set to any custom subclass that accepts the db as its first argument and
       is a context manager that does whatever installation is needed and commits
       the transaction.

    :keyword dict installer_kwargs: Keyword arguments to pass to the *installer_factory*
    """
    assert bool(args) ^ bool(kwargs), "Cannot mix keyword arguments and regular arguments."

    installer_factory = kwargs.pop('installer_factory', persistent_site_trans)
    installer_kwargs = kwargs.pop('installer_kwargs', {})
    db_factory = kwargs.pop('db_factory', default_db_factory)
    assert not kwargs
    assert len(args) == 1 or not args

    func_factory = lambda func: _mock_ds_wrapper_for(func,
                                                     installer_factory,
                                                     installer_kwargs,
                                                     db_factory)
    if len(args) == 1:
        # Being used as a plain decorator
        return func_factory(args[0])
    return func_factory


class SharedConfiguringTestLayer(zodb.ZODBLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin):
    """
    A test layer that configures this package, and sets other useful
    test settings.

    Note that the details of the test settings may change. In this version,
    this configures the :class:`~.BTreeLocalAdapterRegistry` to immediately
    switch to BTrees instead of dicts.
    """

    set_up_packages = ('nti.site',)

    #: The test (a :class:`unittest.TestCase` subclass) currently
    #: executing in this layer. If there is no such test, this is `None`.
    current_test = None

    @classmethod
    def setUp(cls):
        setHooks()
        cls.setUpPackages()
        # Force all the thresholds low so that we do as much testing as possible
        # with btrees.
        from .site import BTreeLocalAdapterRegistry
        from .folder import HostPolicySiteManager
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
        from .site import BTreeLocalAdapterRegistry
        from .folder import HostPolicySiteManager
        del HostPolicySiteManager.btree_threshold
        assert hasattr(HostPolicySiteManager, 'btree_threshold')
        BTreeLocalAdapterRegistry.btree_provided_threshold = cls._orig_provided
        BTreeLocalAdapterRegistry.btree_map_threshold = cls._orig_map
        cls.tearDownPackages()
        zope.testing.cleanup.cleanUp()

    @classmethod
    def testSetUp(cls, test=None): # pylint:disable=arguments-differ
        """
        Tests that run in this layer have their ``db`` property set to the
        current ``db`` of this layer.
        """
        setHooks()
        cls.current_test = test = test or find_test()
        test.db = cls.db

    @classmethod
    def testTearDown(cls):
        """
        When a test in this layer is torn down, its ``db`` property is set
        to ``None``, as is this layer's :attr:`current_test`.
        """
        cls.current_test.db = None
        cls.current_test = None



class SiteTestCase(unittest.TestCase):
    """
    A test case that runs in the :class:`SharedConfiguringTestLayer`.
    """
    layer = SharedConfiguringTestLayer
