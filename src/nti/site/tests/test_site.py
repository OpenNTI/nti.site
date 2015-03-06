#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import raises
from hamcrest import calling
from hamcrest import contains
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
does_not = is_not

import unittest

from zope import interface
from zope.interface import ro
from zope.interface import Interface

from zope.component.hooks import getSite, setSite, site as currentSite

from zope.location.interfaces import LocationError

from zope.component import globalSiteManager as BASE

from z3c.baseregistry.baseregistry import BaseComponents

from nti.site.interfaces import IHostPolicyFolder
from nti.site.subscribers import threadSiteSubscriber
from nti.site.transient import HostSiteManager as HSM

from nti.site.tests import SharedConfiguringTestLayer

from nti.testing.matchers import validly_provides

class IMock(Interface):
	pass

@interface.implementer(IMock)
class MockSite(object):
	
	__name__ = None
	__parent__ = None
	
	def __init__( self, site_man=None):
		self.site_man = site_man

	def getSiteManager(self):
		return self.site_man

class IFoo(Interface):
	pass

class TestSiteSubscriber(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def testProxyHostComps(self):
		pers_comps = BaseComponents(BASE, 'persistent', (BASE,) )
		host_comps = BaseComponents(BASE, 'example.com', (BASE,) )
		host_sm = HSM( 'example.com', 'siteman', host_comps, pers_comps )
		host_site = MockSite(host_sm)
		host_site.__name__ = host_sm.__name__
		setSite( host_site )

		new_comps = BaseComponents(BASE, 'sub_site', (pers_comps,) )
		new_site = MockSite(new_comps)
		new_site.__name__ = new_comps.__name__
		interface.alsoProvides( new_site, IFoo )

		threadSiteSubscriber( new_site, None )

		cur_site = getSite()
		# It should implement the static and dynamic
		# ifaces
		assert_that( cur_site, validly_provides(IFoo) )
		assert_that( cur_site, validly_provides(IMock) )

		# It should have the marker property
		assert_that( cur_site.getSiteManager(),
					 has_property( 'host_components',
								   host_comps ) )

		assert_that( ro.ro( cur_site.getSiteManager() ),
					 contains(
						 # The first entry is synthesized
						 has_property( '__name__', new_comps.__name__),
						 pers_comps,
						 # The host comps appear after all the bases
						 # in the ro of the new site
						 host_comps,
						 BASE ) )

	def testTraverseFailsIntoSiblingSiteExceptHostPolicyFolders(self):
		new_comps = BaseComponents(BASE, 'sub_site', () )
		new_site = MockSite(new_comps)
		new_site.__name__ = new_comps.__name__

		with currentSite(None):
			threadSiteSubscriber(new_site,None)
			# If we walk into a site...

			# ...and then try to walk into a sibling site with no apparent relationship...
			new_comps2 = BaseComponents(BASE, 'sub_site', (new_comps,) )
			new_site2 = MockSite(new_comps2)
			new_site2.__name__ = new_comps2.__name__

			# ... we fail...
			assert_that(calling(threadSiteSubscriber).with_args(new_site2, None),
						raises(LocationError))

			# ...unless they are both HostPolicyFolders...
			interface.alsoProvides(new_site, IHostPolicyFolder)
			interface.alsoProvides(new_site2, IHostPolicyFolder)
			threadSiteSubscriber(new_site2,None)

			# ... which does not change the site
			assert_that( getSite(), is_(same_instance(new_site)) )
