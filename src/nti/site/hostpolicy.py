#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for host policies.

This contains the main unique functionality for this package.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types

from zope import lifecycleevent
from zope import component
from zope import interface

from zope.component.hooks import site as current_site
from zope.component.interfaces import IComponents
from zope.component.interfaces import ISite

from zope.interface import ro
from zope.interface.interfaces import ComponentLookupError

from zope.traversing.interfaces import IEtcNamespace


from zope.site.folder import Folder
from zope.site.folder import rootFolder

from .folder import HostPolicyFolder
from .folder import HostPolicySiteManager
from .folder import HostSitesFolder
from .interfaces import IMainApplicationFolder
from .site import BTreeLocalSiteManager


def synchronize_host_policies():
    """
    Called within a transaction with a site being the current application
    site, find any :mod:`z3c.baseregistry` components that
    should be persistent sites, and register them in the database.

    As a prerequisite, :func:`install_sites_folder` must have been done, and
    we must be in that site.
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
    #   S1
    #   \
    #     S2
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
                continue # pragma: no cover
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


def install_sites_folder(server_folder):
    """
    Given a :class:`.IMainApplicationFolder` that has a site manager,
    install a host sites folder.
    """
    sites = HostSitesFolder()
    str(sites) # coverage
    repr(sites) # coverage
    server_folder['++etc++hostsites'] = sites
    lsm = server_folder.getSiteManager()
    lsm.registerUtility(sites, provided=IEtcNamespace, name='hostsites')
    # synchronize_host_policies()

def install_main_application_and_sites(conn,
                                       root_name=u'Application',
                                       root_alias=u'nti.dataserver_root',
                                       main_name=u'dataserver2',
                                       main_alias=u'nti.dataserver',
                                       main_factory=Folder,
                                       main_setup=None):
    """
    Install the main application and site folder structure into ZODB.

    When this completes, the ZODB root object will have a :class:`.IRootFolder`
    object at "Application" (and optionally at *root_alias*). This will
    have a site manager.

    The root folder in turn will have a
    :class:`.IMainApplicationFolder` child named *main_name* (and
    optionally at *main_alias*). It will have a site manager, and in
    this site manager will be the "++etc++hostsites" object used to
    contain host site folders.

    :param conn: The open ZODB connection.
    :keyword str root_name: The main name of the root folder. This generally should
      be left as "Application" as that's what many Zope 3 components expect.
    :keyword main_factory: The factory that will be used for the :class:`.IMainApplicationFolder`.
      If it produces an object that doesn't implement this interface, it will still
      be marked as doing so.
    :keyword callable main_setup: If given, a callable that will accept the main
      application folder object and perform further setup on it. This will be called
      *before* any lifecycle events are generated. This is a good time to install additional
      utilities, such as :class:`IIntId` utilities.
    """
    root = conn.root()

    # The root folder
    root_folder = rootFolder()
    # NOTE that the root_folder doesn't get a __name__!
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

    server_folder = main_factory()
    if not IMainApplicationFolder.providedBy(server_folder):
        interface.alsoProvides(server_folder, IMainApplicationFolder)
    conn.add(server_folder)
    root_folder[main_name] = server_folder
    assert server_folder.__parent__ is root_folder
    assert server_folder.__name__ == main_name
    assert root_folder[main_name] is server_folder

    lsm = BTreeLocalSiteManager(server_folder)
    conn.add(lsm)
    assert lsm.__parent__ is server_folder
    assert lsm.__bases__ == (root_sm,)

    server_folder.setSiteManager(lsm)
    assert ISite.providedBy(server_folder)

    with current_site(server_folder):
        assert component.getSiteManager() is lsm, "Component hooks must have been reset"

        # The name that many Zope components assume
        root[root_name] = root_folder
        if root_alias:
            root[root_alias] = server_folder

        root[server_folder.__name__] = server_folder
        if main_alias:
            root[main_alias] = server_folder

        if main_setup:
            main_setup(server_folder)

        lifecycleevent.added(root_folder)
        lifecycleevent.added(server_folder)

        install_sites_folder(server_folder)

    return root_folder, server_folder

def get_all_host_sites():
    """
    The order in which sites are accessed is top-down breadth-first,
    that is, the shallowest to the deepest nested sites. This allows
    you to assume that your parent sites have already been updated.

    :returns: A list of sites
    :rtype: list
    """

    sites = component.getUtility(IEtcNamespace, name='hostsites')
    sites = list(sites.values())

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
                ordered.append(base_site)
    return ordered

def run_job_in_all_host_sites(func):
    """
    While already operating inside of a transaction and the application
    environment, execute the callable given by ``func`` once for each
    persistent, registered host (see :func:`synchronize_host_policies`).
    The callable is run with that site current.

    This is typically used to make configuration changes/adjustments
    to utilities local within each site, while the appropriate event
    listeners for the site also fire.

    You are responsible for transaction management.

    :raises: Whatever the callable raises.
    :returns: A list of pairs `(site, result)` containing each site
        and the result of running the function in that site.
    :rtype: list
    """

    logger.debug("Asked to run job %s in ALL sites", func)

    results = list()
    ordered = get_all_host_sites()
    for site in ordered:
        results.append(run_job_in_host_site(site, func))
    return results

def get_host_site(site_name, safe=False):
    """
    Find the persistent site named *site_name* and return it.

    :keyword bool safe: If True, silently ignore any errors.
      **DO NOT** use this param. Deprecated and dangerous.
    """
    site = str(site_name)
    try:
        sites = component.getUtility(IEtcNamespace, name='hostsites')
        result = sites[site]
        return result
    except (ComponentLookupError, KeyError):
        if not safe:
            raise
    return None
get_site = get_host_site  # BWC

def run_job_in_host_site(site, func):
    """
    Helper function to run the *func* with the given site
    as the current site.

    :param site: Either the site object itself, or its unique name.
    """
    site = get_host_site(site) if isinstance(site, string_types) else site
    logger.debug('Running job %s in site %s', func, site.__name__)
    with current_site(site):
        result = func()
        return result
