#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division

__docformat__ = "restructuredtext en"

from nti.testing import zodb

from .. import testing


current_db_site_trans = testing.persistent_site_trans # BWC, remove in 2021
mock_db_trans = current_db_site_trans # BWC, remove in 2021
reset_db_caches = zodb.reset_db_caches # BWC, remove in 2021
WithMockDS = testing.uses_independent_db_site # BWC, remove in 2021
SharedConfiguringTestLayer = testing.SharedConfiguringTestLayer # BWC, remove in 2021
SiteTestCase = testing.SiteTestCase # BWC, remove in 2021
