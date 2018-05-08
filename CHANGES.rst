Changelog for onadata
=====================

1.14.2 (Unreleased)
--------------------


1.14.1 (2018-05-07)
--------------------

- Fix decimal filter for dataview
  `Issue 1393 <https://github.com/onaio/onadata/pull/1393>`_
  [wambere]

- Update google-exports to v0.6
  [wambere]

1.14.0 (2018-05-03)
--------------------

- Python 3 support
  `Issue 1295 <https://github.com/onaio/onadata/pull/1295>`_
  [moshthepitt, pld, wambere]

- Add TLS support to messaging
  `Issue 1366 <https://github.com/onaio/onadata/pull/1366>`_
  [ukanga]

- Add date format to submission time filter for forms
  `Issue 1374 <https://github.com/onaio/onadata/pull/1374>`_
  [wambere]

- Update copyright year to 2018
  `Issue 1376 <https://github.com/onaio/onadata/pull/1376>`_
  [pld]

- Catch IOError when saving osm data
  `Issue 1382 <https://github.com/onaio/onadata/pull/1382>`_
  [wambere]

- Remove deleted dataviews from project page
  `Issue 1383 <https://github.com/onaio/onadata/pull/1383>`_
  [wambere]

- Add deleted by field to projects
  `Issue 1384 <https://github.com/onaio/onadata/pull/1384>`_
  [wambere]

- Add check if user has permission to add a project to a profile
  `Issue 1385 <https://github.com/onaio/onadata/pull/1385>`_
  [ukanga]

- Remove note field from csv export appearing in repeat groups
  `Issue 1388 <https://github.com/onaio/onadata/pull/1388>`_
  [wambere]

- Add created by field to cloned forms
  `Issue 1389 <https://github.com/onaio/onadata/pull/1389>`_
  [wambere]

1.13.2 (2018-04-11)
--------------------

- Bump pyxform version to 0.11.1
  `Issue 1355 <https://github.com/onaio/onadata/pull/1355>`_
  [ukanga]

- Update privacy policy to point to hosted privacy policy, tos, and license
  `Issue 1360 <https://github.com/onaio/onadata/pull/1360>`_
  [pld]

- Use resource_name responses for responses endpoint
  `Issue 1362 <https://github.com/onaio/onadata/pull/1362>`_
  [ukanga]



1.13.1 (2018-04-04)
-------------------

- Refactor JSON streaming on data endpoints and removal of X-Total Header
  `Issue 1290 <https://github.com/onaio/onadata/pull/1290>`_
  [wambere]

- Handle Integrity error on creating a project with the same name
  `Issue 928 <https://github.com/onaio/onadata/issues/928>`_
  [wambere]

- Add OSM tags as fields in Excel, SAV/SPSS, CSV zipped exports
  `Issue 1182 <https://github.com/onaio/onadata/issues/1182>`_
  [wambere]

- Delete filtered datasets linked to a form when deleting a form
  `Issue 964 <https://github.com/onaio/onadata/issues/964>`_
  [wambere]

- Add timestamp to Messaging
  `Issue 1332 <https://github.com/onaio/onadata/issues/1332>`_
  [moshthepitt]

- Update messaging schema for forms to include metadata of the form.
  `Issue 1331 <https://github.com/onaio/onadata/issues/1331>`_
  [moshthepitt]

- Improve setup.py and dependency management
  `Issue 1330 <https://github.com/onaio/onadata/issues/1330>`_
  [moshthepitt]


