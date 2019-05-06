#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Subscribers for traversal events to ensure that the the proper
site is installed, including respecting global registered components.

.. caution:: :func:`zope.site.site.threadSiteSubscriber` also exists and is
   configured by some packages like :mod:`zope.app.publication`. Care must be used to
   ensure that it is *not* configured in place of our own :func:`threadSiteSubscriber`.
"""

# turn off warning for not calling superclass, calling indirect superclass and
# accessing protected methods. we're deliberately doing both
# pylint: disable=W0233,W0231,W0212

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.component.hooks import getSite
from zope.component.hooks import setSite

from zope.interface.interfaces import IComponents

from zope.component.interfaces import ISite

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope.location.interfaces import LocationError

from zope.proxy import ProxyBase
from zope.proxy import non_overridable

from zope.site.interfaces import IRootFolder
from zope.site.interfaces import INewLocalSite

from zope.traversing.interfaces import IBeforeTraverseEvent

from nti.site.interfaces import IHostPolicyFolder
from nti.site.interfaces import IMainApplicationFolder

from nti.site.transient import BasedSiteManager

from nti.site.utils import unregisterUtility


class _ProxyTraversedSite(ProxyBase):
    """
    We need to be able to control the site manager used
    by sites we traverse to in order to ensure that host
    configuration is at the right place in the resolution order.
    But a site can be literally any type of object. So we fake out the
    siteManager methods but proxy everything else.
    """

    def __new__(cls, base, site_manager):
        return ProxyBase.__new__(cls, base)

    def __init__(self, base, site_manager):
        ProxyBase.__init__(self, base)
        self.__site_manager = site_manager

    @non_overridable
    def getSiteManager(self):
        return self.__site_manager

    @non_overridable
    def setSiteManager(self, new_man):
        raise ValueError("Cannot set site manager on proxy")

@component.adapter(ISite, IBeforeTraverseEvent)
def threadSiteSubscriber(new_site, event):
    """
    Set the current ``zope.component.hooks`` site to
    the ``new_site`` object found during traversal,
    being careful to maintain any previously installed host (site-name)
    configurations as lower priority than the new site.

    Sites encountered during traversal are expected to have the
    main application site (e.g., ``nti.dataserver``) in their base chain
    so we have access to its configuration and persistent utilities.
    This implies that sites encountered during traversal are either
    synthetic (generated by a traversal adapter to use some particular
    ``IComponents``)  or themselves persistent.

    Because of this, when we encounter the root or dataserver folders
    as sites, we take no action.

    We expect that something else takes care of clearing the site.
    """

    if IMainApplicationFolder.providedBy(new_site) or IRootFolder.providedBy(new_site):
        # TODO: Since we get these events, we could
        # actually replace nti.appserver.tweens.zope_site_tween
        # with this. That's probably the longterm answer.
        return

    current_site = getSite()
    if current_site is None:
        # Nothing to do
        setSite(new_site)
    elif current_site is new_site:
        # This is typically the case when we traverse directly
        # into utilities registered with the site, for example
        #   /dataserver2/++etc++hostsites/janux.ou.edu/++etc++site/SOMEUTILITY/...
        # with the current host being janux.ou.edu.
        pass
    elif IHostPolicyFolder.providedBy(current_site) and \
         IHostPolicyFolder.providedBy(new_site):
        # This is typically the case when we traverse directly
        # into utilities registered with the site, for example
        #   /dataserver2/++etc++hostsites/janux.ou.edu/++etc++site/SOMEUTILITY/...
        # with the current host NOT being janux.ou.edu.
        # We do not want to switch host configurations here, but we do
        # want to allow traversal, so we take no action.
        # TODO: We might want to only allow this if there is some
        # inheritance relationship between the two sites?
        pass
    elif hasattr(current_site.getSiteManager(), 'host_components'):
        # A site synthesized by get_site_for_site_names
        # OR one previously synthesized by this function. In either case,
        # we always want to proxy, putting the preserved host components
        # at the end of the new proxy RO.
        host_components = current_site.getSiteManager().host_components
        # We need to keep host_components in the bases
        # for the new site. Where to put it is tricky
        # if we want to support multiple layers of overriding
        # of host registrations. Fortunately, the zope.interface.ro
        # machinery does exactly the right thing if we tack host
        # components (which are probably not already in the list)
        # on to the end. If they are in the list already, they
        # stay where they were.
        new_bases = new_site.getSiteManager().__bases__ + (host_components,)
        # TODO: We don't need to proxy the site manager, right?
        # it's almost never special by itself...
        new_site_manager = BasedSiteManager(new_site.__parent__,
                                            new_site.__name__,
                                            new_bases)
        new_site_manager.host_components = host_components
        new_fake_site = _ProxyTraversedSite(new_site,
                                            new_site_manager)

        setSite(new_fake_site)
    else:
        # Cancel traversal using a LocationError. This typically
        # will get surfaced as a 404.
        raise LocationError("Unknown kind of site", new_site, current_site)

@component.adapter(INewLocalSite)
def new_local_site_dispatcher(event):
    """
    Dispatches just like an object event,
    that way we can do things based on the type of the
    site manager.

    Note that if the containing ISite is (re)moved, an
    ObjectEvent will be fired for (sitemanager, site-event);
    that is, you subscribe to the site manager and the object moved
    event, but the event will have the ISite as the object property.
    """
    component.handle(event.manager, event)


@component.adapter(IHostPolicyFolder, IObjectRemovedEvent)
def _on_site_removed(site, unused_event=None):
    """
    Unregister the ``IBaseComponents`` for a removed site.
    .. versionadded:: 1.4.0
    """
    name = site.__name__
    site_components = component.queryUtility(IComponents, name=name)
    if site_components is not None:
        unregisterUtility(component.getSiteManager(),
                          site_components,
                          IComponents,
                          name=name)
