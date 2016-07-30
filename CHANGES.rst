=========
 Changes
=========

1.0.0 (unreleased)
==================

- First PyPI release.
- Add support for Python 3.
- Remove HostPolicySiteManager.subscribedRegisterUtility and
  subscribeUnregisterUtility. See :issue:`5`. This may be a small
  performance regression in large sites. If so we'll find a different
  way to deal with it.
- Remove HostSitesFolder._delitemf. It was unused and buggy.
- Add BTreesLocalSiteManager to automatically switch internal
  registration data to BTrees when possible and necessary. See issue #4.
