#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for host policies.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.interface import ro

from zope import component
from zope.component.interfaces import IComponents
from zope.component.hooks import site as current_site

from zope.traversing.interfaces import IEtcNamespace

from .folder import HostPolicyFolder
from .folder import HostPolicySiteManager

from .interfaces import IMainApplicationFolder

def synchronize_host_policies():
	"""
	Called within a transaction with a site being the current dataserver
	site, find any :mod:`z3c.baseregistry` components that
	should be sites, and register them in the database.
	"""

	# TODO: We will ultimately need to deal with removing and renaming
	# of these

	# Resolution order: The actual ISite __parent__ order is not
	# important, so we can keep them flat to mirror the GSM IComponents
	# registrations. What matters is the __bases__ of the site managers.
	# Now, if the global IComponents are themselves flat, then it doesn't matter;
	# however, if you have a hierarchy (and we do) then it matters critically, because
	# we need to pick up persistent utilities from these objects, as well as
	# the global components, in the right order. For example, if we have this
	# global hierarchy:
	#  GSM
	#  \
	#	S1
	#    \
	#	  S2
	# and in the database we have the nti.dataserver and root persistent site managers,
	# then when we create the persistent sites for S1 and S2 (PS1 and PS2) we want 
	# the resolution order to be:
	#   PS2 -> S2 -> PS1 -> S1 -> DS -> Root -> GSM
	# That is, we need to get the persistent components mixed in between the
	# global components.
	# Fortunately this is very easy to achieve. The code in zope.interface.ro handles
	# this.
	# We just need to ensure:
	#   PS1.__bases__ = (S1, DS)
	#   PS2.__bases__ = (S2, PS1)

	sites = component.getUtility(IEtcNamespace, name='hostsites')
	ds_folder = sites.__parent__
	assert IMainApplicationFolder.providedBy(ds_folder)

	ds_site_manager = ds_folder.getSiteManager()

	# Ok, find everything that is globally registered
	global_sm = component.getGlobalSiteManager()
	all_global_named_utilities = list(global_sm.getUtilitiesFor(IComponents))
	for name, comp in all_global_named_utilities:
		# The sites must be registered the same as their internal name
		assert name == comp.__name__
	all_global_utilities = [x[1] for x in all_global_named_utilities]

	# Now, get the resolution order of each site; this is an easy way
	# to do a kind of topological sort.
	site_ros = [ro.ro(x) for x in all_global_utilities]

	# Next, start creating persistent sites in the database, walking from the top
	# of the resolution order (the end of the list)
	# towards the root; the first one we put in the DB gets the DS as its
	# base, otherwise it gets the previous one we put in.

	for site_ro in site_ros:
		site_ro = reversed(site_ro)

		secondary_comps = ds_site_manager
		for comps in site_ro:
			name = comps.__name__
			logger.debug("Checking host policy for site %s", name)
			if name.endswith('base') or name.startswith('base'):
				# The GSM or the base global objects
				# TODO: better way to do this...marker interface?
				continue
			if name in sites:
				logger.debug("Host policy for %s already in place", name)
				# Ok, we've already put one in for this level.
				# We need to make it our next choice going forward
				secondary_comps = sites[name].getSiteManager()
			else:
				# Great, create the site
				logger.info("Installing site policy %s", name)

				site = HostPolicyFolder()
				# should fire object created event
				sites[name] = site

				site_policy = HostPolicySiteManager(site)
				site_policy.__bases__ = (comps, secondary_comps)
				# should fire INewLocalSite
				site.setSiteManager(site_policy)
				secondary_comps = site_policy

def run_job_in_all_host_sites(func):
	"""
	While already operating inside of a transaction and the dataserver
	environment, execute the callable given by ``func`` once for each
	persistent, registered host (see ;func:`synchronize_host_policies`).
	The callable is run with that site current.

	The order in which sites are accessed is top-down breadth-first,
	that is, the shallowest to the deepest nested sites. This allows
	you to assume that your parent sites have already been updated.

	This is typically used to make configuration changes/adjustments
	to utilities local within each site, while the appropriate event
	listeners for the site also fire.

	You are responsible for transaction management.

	:raises: Whatever the callable raises.
	:returns: A list of pairs `(site, result)` containing each site
		and the result of running the function in that site.
	:rtype: list
	"""

	sites = component.getUtility(IEtcNamespace, name='hostsites')
	sites = list(sites.values())
	logger.debug("Asked to run job %s in ALL sites", func)

	# The easyiest way to go top-down is to again use the resolution order;
	# we just have to watch out for duplicates and non-persistent components
	site_to_ro = {site: ro.ro(site.getSiteManager()) for site in sites}

	# This should be a plain, directed acyclic tree (single root) that is now
	# linearized.
	# Transform from the site manager back into the site object itself
	site_to_site_ro = {}
	for site, managers in site_to_ro.items():
		site_to_site_ro[site] = [getattr(x, '__parent__', None) for x in managers]

	# Ok, now, go through the dictionary, walking from the top to the bottom,
	# one at a time, thus producing the correct order
	# (Because our datastructure looks like this:
	#   site1: [site1, ds, base, GSM]
	#   site2: [site2, site1, base, GSM]
	#   site3: [site3, ds, base, GSM])
	ordered = list()

	while site_to_site_ro:
		for site, managers in dict(site_to_site_ro).items():
			if not managers:
				site_to_site_ro.pop(site)
				continue

			base_site = managers.pop()
			if base_site in sites and base_site not in ordered:
				# Ie., it's a real one we haven't seen before
				ordered.append( base_site )

	results = list()
	for site in ordered:
		logger.debug('Running job %s in site %s', func, site.__name__)
		with current_site(site):
			result = func()
			results.append( (site, result) )
	return results
