Changelog for onadata
=====================

1.14.4 (2018-06-21)
-------------------

-  Support exporting labels for selects in the data.
  `Issue 1427 <https://github.com/onaio/onadata/issues/1427>`_
  [ukanga]

-  Handle UnreadablePostError exception in submissions..
  `Issue 847 <https://github.com/onaio/onadata/issues/847>`_
  [ukanga]

- Support download of CSV XLSForm,
  `Commit 4abd30d <https://github.com/onaio/onadata/commit/4abd30d851512e1e8ab03a350f1869ebcbb4b9bf>`_
  [ukanga]

1.14.3 (2018-05-30)
-------------------

- Support value_select_multiples option in flat CSV, support binary_select_multiples option in API exports.
  `Issue 1409 <https://github.com/onaio/onadata/issues/1409>`_
  [ukanga]

- Check the value of the variable remove when sharing a project with team or
  collaborators, and only remove if value is true
  `Issue 1415 <https://github.com/onaio/onadata/pull/1415>`_
  [wambere]

- Fix TypeError on SPPS Exports with external choices.
  `Issue 1410 <https://github.com/onaio/onadata/issues/1410>`_
  [ukanga]

- Generate XForm hash after every XML change has been applied.
  `Issue 1417 <https://github.com/onaio/onadata/issues/1417>`_
  [ukanga]

- Add api/v1/profiles/[username]/monthly_submissions endpoint.
  `Issue 1423 <https://github.com/onaio/onadata/pull/1423>`_
  [wambere]

- Show metadata only to the owner
  `Issue 1416 <https://github.com/onaio/onadata/issues/1416>`_
  [ukanga]

-  Return flow results response timestamp in rfc3339 format explicitly
  `Issue 1420 <https://github.com/onaio/onadata/issues/1420>`_
  [ukanga]

1.14.2 (2018-05-14)
--------------------

- Update check_xform_uuid() to only check for non deleted forms
  `Issue 1403 <https://github.com/onaio/onadata/issues/1403>`_
  [ukanga]

- Persist Flow Results Contact ID and Session ID
  `Issue 1398 <https://github.com/onaio/onadata/pull/1398>`_
  [ukanga]

- Include form version in ODK formList endpoint
  `Issue 1195 <https://github.com/onaio/onadata/issues/1195>`_
  [ukanga]

- Reorder how attachments are saved
  `Issue 961 <https://github.com/onaio/onadata/issues/961>`_
  [wambere]

1.14.1 (2018-05-07)
--------------------

- Fix decimal filter for dataview
  `Issue 1393 <https://github.com/onaio/onadata/pull/1393>`_
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


