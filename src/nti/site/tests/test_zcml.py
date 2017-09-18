#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import not_none
from hamcrest import assert_that

from zope import component

from nti.site.interfaces import ISiteMapping

from nti.testing.base import ConfiguringTestBase

ZCML_STRING = """
<configure  xmlns="http://namespaces.zope.org/zope"
            xmlns:i18n="http://namespaces.zope.org/i18n"
            xmlns:zcml="http://namespaces.zope.org/zcml"
            xmlns:sites="http://nextthought.com/sites">

    <include package="zope.component" file="meta.zcml" />
    <include package="zope.security" file="meta.zcml" />
    <include package="zope.component" />
    <include package="." file="meta.zcml" />

    <configure>
        <sites:registerSiteMapping source_site_name="mySite1"
                                   target_site_name="mySite2" />
    </configure>
</configure>

"""


class TestZcml(ConfiguringTestBase):

    def test_registration(self):
        self.configure_string(ZCML_STRING)
        site_mapping = component.queryUtility(ISiteMapping, name='mySite1')
        assert_that(site_mapping, not_none())
        assert_that(site_mapping.source_site_name, is_('mySite1'))
        assert_that(site_mapping.target_site_name, is_('mySite2'))

        site_mapping = component.queryUtility(ISiteMapping, name='mySite2')
        assert_that(site_mapping, none())
