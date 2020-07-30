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

    def test_print_tree(self):

        class Trans(testing.persistent_site_trans):
            printed = None
            def on_application_and_sites_installed(self, folder):
                super(Trans, self).on_application_and_sites_installed(folder)
                folder._p_jar.root()['key'] = 'value'
                self.printed = testing.format_tree(folder._p_jar.root())


        # open for the side-effects
        t = Trans(testing.default_db_factory())
        with t:
            pass

        printed = t.printed

        self.assertIn('<Connection Root Dictionary>', printed)
        self.assertIn('<ISite,IRootFolder>: Application', printed)
        self.assertIn('<ISite,IMainApplicationFolder>: dataserver2', printed)
        self.assertIn('dataserver2 -> dataserver2', printed)
        self.assertIn('nti.dataserver -> dataserver2', printed)
        self.assertIn('nti.dataserver_root -> Application', printed)
        self.assertIn('len=', printed)

    def test_print_basic(self):
        printed = testing.format_tree('a string')
        self.assertIn('a string', printed)

    def test_print_no_len(self):
        printed = testing.format_tree(object())
        self.assertNotIn('len=', printed)

    def test_print_unknown_type(self):
        called = []
        def show_unknown(o):
            called.append(42)
            return str(o)

        printed = testing.format_tree(object(), show_unknown=show_unknown)
        self.assertIn('object', printed)
        self.assertEqual(called, [42])

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
