#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helpers for working with local utilities.

A local utility is a (persistent) utility registered in a local (persistent) site
manager. Local utilities need to be traversable and thus are usually children
of the local site manager itself.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from .utils import registerUtility
from .utils import unregisterUtility

def install_utility(utility, utility_name, provided, local_site_manager):
    """
    Call this to install a local utility. Often you will
    do this from inside a handler for the registration of another
    dependent utility (:class:`.IRegistration`).

    The utility should be :class:`.IContained` because it
    will be held inside the site manager.

    :param str utility_name: The *traversal* name of the utility, not
        the component registration name. This currently only handles
        the default, unnamed registration.

    .. seealso:: :func:`install_utility_on_registration`
    """

    # Contain the utilities we are about to install.
    # Note that for queryNextUtility, etc, to work properly if they
    # use themselves as the context (which seems to be what people do)
    # these need to be children of the SiteManager object: qNU walks from
    # the context to the enclosing site manager, and then looks through ITS
    # bases

    local_site_manager[utility_name] = utility
    registerUtility(local_site_manager, utility, provided=provided)

def install_utility_on_registration(utility, utility_name, provided, event):
    """
    Call this to install a local utility in response to the registration
    of another object.

    The utility should be :class:`IContained` because it
    will be held inside the site manager.

    :param event: The :class:`.IRegistered` event
    """

    registration = event.object
    local_site_manager = registration.registry
    install_utility(utility, utility_name, provided, local_site_manager)

def uninstall_utility_on_unregistration(utility_name, provided, event):
    """
    When a dependent object is unregistered, this undoes the
    work done by :func:`install_utility`.

    :param str utility_name: The *traversal* name of the utility, not
        the component registration name. This currently only handles
        the default, unnamed registration.

    """

    registration = event.object
    local_site_manager = registration.registry

    child_component = local_site_manager[utility_name]

    looked_up = local_site_manager.getUtility(provided)
    assert looked_up is child_component, (looked_up, child_component)

    unregisterUtility(local_site_manager, child_component, provided=provided)
    del local_site_manager[utility_name]

def queryNextUtility(context, interface, default=None):
    """
    Our persistent sites are a mix of persistent and non-persistent
    bases, with many of them having multiple bases. For example (using
    the notation: name (bases,) [type])::

        example.com (GlobalSiteManager) [global]
        Application (GlobalSiteManager) [persistent]
        site-root.example.com (Application, example.com) [persistent]
        child.example.com (example.com) [global]
        site-child.example.com (child.example.com, site-root.example.com) [persistent]

    This gives site-child.example.com this (correct) resolution order::

        site-child.example.com, child.example.com, site-root.example,com Application, example.com, GSM

    However, :func:`zope.component.queryNextUtility` only looks in the *first* base to find
    a next utility. Therefore, when site-janux.ou.edu asks for a next utility,
    instead of getting something persistent from site-platform.ou.edu,
    it instead gets the global non-persistent version from platform.ou.edu.

    We don't generally want to change the resolution order, but we do need
    to tweak it here for getting next utilities so that we consider
    persistent things first. Note that this breaks down if we have
    utilities registered both persistently and non-persistently at the same level.
    """

    try:
        sm = component.getSiteManager(context)
    except LookupError:
        return default

    # These are returned starting from the GlobalSiteManager
    # and working down the resolution chain
    all_utilities = sm.getAllUtilitiesRegisteredFor(interface)
    if not all_utilities:
        return default

    try:
        me = all_utilities.index(context)
        next_ = me - 1
    except ValueError:
        # Not in it. That means our site manager is the global site manager,
        # and we hit the global catalog
        assert sm == component.getGlobalSiteManager()
        next_ = 0

    result = default
    if next_ >= 0:
        result = all_utilities[next_]
        if result is context:
            # in the GSM, we're querying for the GSM utility?
            # Terminate with default to avoid an infinite loop
            result = default # pragma: no cover
    return result
