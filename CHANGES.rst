=========
 Changes
=========

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
