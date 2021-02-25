=========
 Changes
=========

2.4.0 (2021-02-25)
==================

- Substantially reduce the thresholds at which the
  ``BTreePersistentComponents`` will convert internal data structures
  from plain ``dict`` objects into ``BTree`` objects. This is intended
  to reduce the pickle size of, and number of ghost objects created
  by, components containing many utilities. Previously, the thresholds
  were set very high and mostly worked for sites with many adapters.

- Add support for Python 3.9.

- Move to Github Actions from Travis CI.

2.3.0 (2020-09-11)
==================

- Make ``threadSiteSubscriber`` (the traversal subscriber for
  ``ISite`` objects) will install a traversed site that is a root if
  there is no current site.

  Previously, it never installed root sites.

- Make ``threadSiteSubscriber`` install sites when their configuration
  is not recognized.

  Previously, it would raise ``LocationError``.

- Fix tests with, and require, zope.site 4.4.0 or above. See
  :issue:`34`.

- Fix deprecation warning from ``nti.transactions``. Requires
  ``nti.transactions`` 4.0. See :issue:`33`.

2.2.0 (2020-07-30)
==================

- Improvements and bug fixes to ``nti.testing.print_tree``.


2.1.0 (2020-06-17)
==================

- Test changes: Depend on ``nti.testing`` 3.0 and refactor certain
  internal test methods for improved isolation. The dependency on
  ZODB is now >= 5.6.0.

  Some internal, undocumented test attributes (``current_mock_db``, a
  ZODB.DB, and ``current_transaction`` which was actually a ZODB
  Connection) have been removed. The former is replaced with
  ``nti.testing.zodb.ZODBLayer.db``, and there is no replacement for
  the later.

- Add the module ``nti.site.testing``. This contains extensible,
  documnted versions of the functions that were previously in
  ``nti.site.tests`` as private helpers.

- Add support for Python 3.8.

- Make ``hostpolicy.install_main_application_and_sites()`` set the
  *root_alias* correctly. Previously, instead of setting it to the
  *root_name*, it set it to the *main_name*.

2.0.0 (2019-09-10)
==================

- Update ``run_job_in_site`` to work with nti.transactions 3.0 and
  enable the optimizations of an explicit transaction manager.

- Test support for Python 3.7.

- Stop claiming support for Python 3.4 or 3.5; those aren't tested.

- Test support for PyPy3.

1.4.0 (2019-05-06)
==================

- Add subscriber to unregister ``IBaseComponents`` on host policy folder
  removal.


1.3.0 (2017-11-16)
==================

- Allow ``ISiteMapping`` to map between persistent sites.


1.2.0 (2017-09-18)
==================

- Add the ability to map one (non-persistent) site to another via
  configuration. If ``get_site_for_site_names`` does not find
  persistent site components for a site, it will fall back to looking
  for a configured ``ISiteMapping`` pointing to another target site.


1.1.0 (2017-06-14)
==================

- Require zope.interface 4.4.2 or greater; 4.4.1 has regressions.

- Require transaction >= 2.1.2 for its more relaxed handling of text
  or byte meta data.

- Require BTrees >= 4.3.2 for its relaxed handling of objects with
  default comparison.

1.0.3 (2016-11-21)
==================

- ``run_job_in_site`` now supports :func:`functools.partial` objects
  and other callables that don't have a ``__name__`` and/or
  ``__doc__``. See :issue:`16`.


1.0.2 (2016-11-21)
==================

- Support for transaction 2.0, and fix a lurking UnicodeError under
  Python 3. See :issue:`14`.


1.0.1 (2016-09-08)
==================

- If you are using zope.interface 4.3.0 or greater, you can register
  utilities and adapters using ``implementedBy`` (so bare classes) in
  a BTreeLocalSiteManager. Otherwise, using an older version, you'll
  get a TypeError and may be unable to complete the registration or
  transition to BTrees, and the map data may be inconsistent.


1.0.0 (2016-08-02)
==================

- First PyPI release.
- Add support for Python 3.
- Remove HostPolicySiteManager.subscribedRegisterUtility and
  subscribeUnregisterUtility. See :issue:`5`. This may be a small
  performance regression in large sites. If so we'll find a different
  way to deal with it.
- Remove HostSitesFolder._delitemf. It was unused and buggy.
- Add BTreesLocalSiteManager to automatically switch internal
  registration data to BTrees when possible and necessary. See :issue:`4`.
- Add :func:`nti.site.hostpolicy.install_main_application_and_sites`
  for setting up a database. See :issue:`9`.
