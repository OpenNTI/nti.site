# -*- coding: utf-8 -*-
"""
Tests for nti.site.tests.testing.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

from nti.site import testing

class TestPrintTree(unittest.TestCase):

    def setUp(self):
        super(TestPrintTree, self).setUp()
        testing.setHooks()

    def tearDown(self):
        testing.resetHooks()
        super(TestPrintTree, self).tearDown()
    if bytes is str:
        # Python 2. Use something that automatically encodes unicode
        # and also accepts bytes.
        from cStringIO import StringIO as NativeIO
    else:
        from io import StringIO as NativeIO

    def test_print_tree(self):
        buf = self.NativeIO()

        class Trans(testing.persistent_site_trans):

            def on_application_and_sites_installed(self, folder):
                super(Trans, self).on_application_and_sites_installed(folder)
                folder._p_jar.root()['key'] = 'value'
                testing.print_tree(folder._p_jar.root(), file=buf)


        # open for the side-effects
        with Trans(testing.default_db_factory()):
            pass

        printed = buf.getvalue()
        self.assertIn('<Connection Root Dictionary>', printed)
        self.assertIn('<ISite,IRootFolder>: Application', printed)
        self.assertIn('<ISite,IMainApplicationFolder>: dataserver2', printed)
        self.assertIn('dataserver2 -> dataserver2', printed)
        self.assertIn('nti.dataserver -> dataserver2', printed)
        self.assertIn('nti.dataserver_root -> Application', printed)

    def test_print_basic(self):
        buf = self.NativeIO()
        testing.print_tree('a string', file=buf)
        printed = buf.getvalue()
        self.assertIn('a string', printed)

class TestCurrentDBSiteTrans(testing.SiteTestCase):

    def test_find_site(self):
        with testing.persistent_site_trans(site_name='foobar'):
            pass

class TestIndependent(unittest.TestCase):

    @testing.uses_independent_db_site
    def test_sets_db_no_layer(self):
        self.assertTrue(hasattr(self, 'db'))

    @testing.uses_independent_db_site(installer_kwargs={'site_name': None})
    def test_keyword_argument(self):
        pass
