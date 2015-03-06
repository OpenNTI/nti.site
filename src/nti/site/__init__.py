#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Addons and additions to the Zope site concept.

Integration between the ZCA ``site`` system, configured site
policies, and the Dataserver.

In the Zope world, sites are objects that can express configuration by
holding onto an instance of IComponents known as its *site manager*.
Typically they are arranged in a tree, with the global site at the
root of the tree. Site managers inherit configuration from their
parents (bases, which may or may not be their ``__parent__``). Often,
they are persistent and part of the traversal tree. One site is the
current site and the ZCA functions (e.g.,
:meth:`.IComponentArchitecture.queryUtility`) apply to that site.

Our application has one persistent site, the dataserver site,
containing persistent utilities (such as the dataserver); see
:mod:`nti.dataserver.generations.install` This site, or a descendent
of it, must always be the current site when executing application
code.

In our application, we also have the concept of site policies,
something that is applied based on virtual hosting. A site policy is
also an ``IComponents``, registered in the global site as a utility
named for the hostname to which it should apply (e.g.,
``mathcounts.nextthought.com``). Historically, these are not
necessarily persistent and part of the traversal tree. Now, we expect
them to be persistent, though they are still not part of the traversal
tree.

Thus there are two things to accomplish: make the dataserver site the
current site, and also construct a site that descends from that site
and contains any applicable policies.


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)
