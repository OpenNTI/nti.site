#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Transient, in-memory, non-persistent site and site manager
implementations. These are used to get non-persistent
host-based global IComponents into the base resolution order.

.. $Id$
"""

# turn off warning for not calling superclass, calling indirect superclass and
# accessing protected methods. we're deliberately doing both
# pylint: disable=W0233,W0231,W0212

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.component import interfaces as comp_interfaces
from zope.component.persistentregistry import PersistentComponents as _ZPersistentComponents

from zope.container.contained import Contained as _ZContained

from zope.site.site import LocalSiteManager as _ZLocalSiteManager

# TODO: All this site mucking may be expensive. It has significant possibilities
# for optimization (caching) using the fact that much of it is read only.

class BasedSiteManager(_ZLocalSiteManager):
    """
    A site manager that exists simply to have bases, but not to
    record itself as children of those bases (since that's unnecessary
    for our purposes and leads to ZODB conflicts).
    """

    # Note that the adapter registries in the base objects /will/ have
    # weak references to this object; it's very hard to stop this. These
    # will stick around until a gc is run. (For testing purposes,
    # it is important to GC or you can get weird errors like:
    # File "zope/interface/adapter.py", line 456, in changed
    #   super(AdapterLookupBase, self).changed(None)
    # File "ZODB/Connection.py", line 857, in setstate
    #   raise ConnectionStateError(msg)
    #  ConfigurationExecutionError: <class 'ZODB.POSException.ConnectionStateError'>:
    #   Shouldn't load state for 0x237f4ee301650a49 when the connection is closed
    # in:
    # File "zope/site/configure.zcml", line 13.4-14.71
    # <implements interface="zope.annotation.interfaces.IAttributeAnnotatable" />
    # Fortunately, Python's GC is precise and refcounting, so as long as we do not leak
    # refs to these, we're fine

    def _setBases(self, bases):
        # Bypass the direct superclass.
        _ZPersistentComponents._setBases(self, bases)

    def __init__(self, site, name, bases):
        # Bypass the direct superclass to avoid setting
        # bases multiple times and initing the BTree portion, which we won't use
        # NOTE: This means we are fairly tightly coupled
        _ZPersistentComponents.__init__(self)

        # Locate the site manager
        self.__parent__ = site
        self.__name__ = name
        self.__bases__ = bases

    def _newContainerData(self):  # pragma: no cover
        return None  # We won't be used as a folder

    def __reduce__(self):
        raise TypeError("BasedSiteManager should not be pickled")

    __getstate__ = __reduce__


class HostSiteManager(BasedSiteManager):
    """
    A site manager that is intended to be used with globally
    registered IComponents plus the application persistent components.
    """

    def __init__(self, site, name, host_components, persistent_components):
        self._host_components = host_components
        self._persistent_components = persistent_components
        BasedSiteManager.__init__(self,
                                  site,
                                  name,
                                  (host_components, persistent_components))

    @property
    def host_components(self):
        return self._host_components

    @property
    def persistent_components(self):
        return self._persistent_components

@interface.implementer(comp_interfaces.ISite)
class TrivialSite(_ZContained):
    """
    Trivial non-persistent implementation of :class:`.ISite`
    """
    def __init__(self, site_manager):
        self._sm = site_manager

    def getSiteManager(self):
        return self._sm

    def __reduce__(self):
        raise TypeError("TrivialSite should not be pickled")
