#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Addons and additions to the Zope site concept.

Integration between the ZCA ``site`` system, configured site
policies, and the persistent database.

In the Zope world, sites are objects that can express configuration by
holding onto an instance of IComponents known as its *site manager*.
Typically they are arranged in a tree, with the global site at the
root of the tree. Site managers inherit configuration from their
parents (bases, which may or may not be their ``__parent__``). Often,
they are persistent and part of the traversal tree. One site is the
current site and the ZCA functions (e.g.,
:meth:`.IComponentArchitecture.queryUtility`) apply to that site.

Our application has one main persistent site, the application site,
containing persistent utilities (such as the application object). This
site, or a descendent of it, must always be the current site when
executing application code.

In our application, we also have the concept of site policies,
something that is applied based on virtual hosting. A site policy is
also an ``IComponents``, registered in the global site as a utility
named for the hostname to which it should apply (e.g.,
``domain.example.com``). Historically, these are not necessarily
persistent and part of the traversal tree. Now, we expect them to be
persistent, though they are still not part of the traversal tree.

Thus there are two things to accomplish: make the application site the
current site, and also construct a site that descends from that site
and contains any applicable policies that are globally configured.

* See :mod:`nti.site.interfaces` for descriptions of the concepts this
  package uses.
* See :mod:`nti.site.hostpolicy` for working with registered and persistent
  site configurations.
* See :mod:`nti.site.site` for the getting the correctly configured site.
* See :mod:`nti.site.subscribers` for setting up the correct site during traversal.
* See :mod:`nti.site.testing` for test helpers.
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# All of these imports are deprecated and will be removed in 2021.

from nti.site.hostpolicy import get_host_site # pylint:disable=unused-import
from nti.site.hostpolicy import get_all_host_sites # pylint:disable=unused-import

from nti.site.utils import registerUtility # pylint:disable=unused-import
from nti.site.utils import unregisterUtility # pylint:disable=unused-import
