Changelog for Onadata
=====================

1.19.4 (2019-04-08)
-------------------
- Expose submissions URL to Enketo.
  `Pull #1526 <https://github.com/onaio/onadata/pull/1526>`_
  [@WinnyTroy and @lincmba]

- Load one image at a time in classic photo view.
  `Fix #1560 <https://github.com/onaio/onadata/issues/1560>`_
  [@lincmba]

- Add transferproject command to transfer project between users.
  `Issue #1491 <https://github.com/onaio/onadata/issues/1491>`_
  [@bmarika]

- Add MetaData.submission_review() function for submission reviews metadata.
  `Fix #1585 <https://github.com/onaio/onadata/issues/1585>`_
  [@lincmba]

- Fixes on ZIP_REPORT_ATTACHMENT_LIMIT
  `Fix #1592 <https://github.com/onaio/onadata/issues/1592>`_
  [@lincmba]

- Fix unicode TypeError on publishing text_xls_form strings.
  `Fix #1593 <https://github.com/onaio/onadata/issues/1593>`_
  [@ukanga]


1.19.3 (2019-03-08)
-----------------------
- Convert excel date format to csv format
  `Fixes #1577 <https://github.com/onaio/onadata/issues/1577>`_
  [@lincmba]

1.19.2 (2019-02-28)
-----------------------
- Optimize attachment query by removing sort and count
  `PR #1578 <https://github.com/onaio/onadata/pull/1578>`_
  [@ukanga]

1.19.1 (2019-02-26)
-----------------------

- Fix TypeError on change_password when format is supplied on URL.
  `PR #1572 <https://github.com/onaio/onadata/pull/1572>`_
  [@bmarika]

1.19.0 (2019-02-21)
-----------------------

- Fix Data Upload Failing
  `Fixes #1561 <https://github.com/onaio/onadata/issues/1561>`_
  [@lincmba]

- Upgrade to pyxform version 0.13.1
  `PR #1570 <https://github.com/onaio/onadata/pull/1570/files>`_
  [@ukanga]

1.18.1 (2019-02-07)
-----------------------

- Pick passed format or default to json in GenericRelatedField serializer
  `PR #1558 <https://github.com/onaio/onadata/pull/1558>`_
  [lincmba]

1.18.0 (2019-01-24)
-----------------------

- Update to pyxform 0.12.2, performance regression fix.
  `Fixes https://github.com/XLSForm/pyxform/issues/247 <https://github.com/XLSForm/pyxform/issues/247>`_
  [ukanga]

- Update projects endpoint API documentation.
  `Fixes #1520 <https://github.com/onaio/onadata/issues/1520>`_
  [lincmba]

- Fix improperly configured URL exception.
  `Fixes #1518 <https://github.com/onaio/onadata/issues/1518>`_
  [lincmba]

- Fix Wrong HTTP method on the project share end point
  `Fixes #1520 <https://github.com/onaio/onadata/issues/1520>`_
  [lincmba]

- Fix files endpoint thumbnail not working for large png images
  `Fixes #1509 <https://github.com/onaio/onadata/issues/1509>`_
  [lincmba]

- Fix recreating the same dataview
  `Fixes #1498 <https://github.com/onaio/onadata/issues/1498>`_
  [lincmba]

- Make sure that when a project is deleted all forms are deleted
  `Fixes #1494 <https://github.com/onaio/onadata/issues/1494>`_
  [bmarika]

- Return better error messages on invalid csv/xls imports
  `Fixes #987 <https://github.com/onaio/onadata/issues/987>`_
  [lincmba]

- Filter media attachments exports
  `Fixes #1028 <https://github.com/onaio/onadata/issues/1028>`_
  [lincmba]

- Remove empty optional fields in formList
  `Fixes #1519 <https://github.com/onaio/onadata/issues/1519>`_
  [lincmba]

- Fix failing bulk csv edits
  `Fixes #1540 <https://github.com/onaio/onadata/issues/1540>`_
  [lincmba]

- Fix TypeError at /api/v1/forms/[pk]/export_async.json
  `Fixes #999 <https://github.com/onaio/onadata/issues/999>`_
  [lincmba]

- Handle DataError during XForms submission
  `Fixes #949 <https://github.com/onaio/onadata/issues/949>`_
  [bmarika]

- Escape apostrophes in SQL queries
  `Fixes #1525 <https://github.com/onaio/onadata/issues/1525>`_
  [bmarika]

- Upgrade kombu
  `PR #1529 <https://github.com/onaio/onadata/pull/1529>`_
  [lincmba]

1.17.0 (2018-12-19)
-------------------

- Fix external Choices with number names
  `Fixes #1485 <https://github.com/onaio/onadata/issues/1485>`_
  [lincmba]

- Remove link expiration message on verification email
  `Fixes #1489 <https://github.com/onaio/onadata/issues/1489>`_
  [lincmba]

- Only generate hash for linked datasets
  `Fixes #1411 <https://github.com/onaio/onadata/issues/1411>`_
  [lincmba]

- Fix merged dataset with deleted parent
  `Fixes #1511 <https://github.com/onaio/onadata/issues/1511>`_
  [lincmba]

- Update/upgrade packages
  `PR 1522 <https://github.com/onaio/onadata/pull/1522>`_
  [lincmba, ukanga]

1.16.0 (2018-12-06)
-------------------

- Fix order extra columns in multiple select exports.
  `Fixes #873 <https://github.com/onaio/onadata/issues/873>`_
  [lincmba]

- Update user roles according to xform meta permissions provided.
  `Fixes #1479 <https://github.com/onaio/onadata/issues/1479>`_
  [lincmba]

- Performance optimisation - use content_type to determine metadata content_object type.
  `Issue #2475 <https://github.com/onaio/onadata/issues/2475>`_
  [ukanga]

- Excel bulk data import support.
  `Issue #1432 <https://github.com/onaio/onadata/issues/1432>`_
  [lincmba]

- Add submission fields to data exports.
  `Issue #1477 <https://github.com/onaio/onadata/issues/1477>`_
  [kahummer]

- Fix error on deleting xform with long id_string or sms_id_string.
  `Issue #1430 <https://github.com/onaio/onadata/issues/1430>`_
  [lincmba]

- Set Default TEMP_TOKEN_EXPIRY_TIME.
  `Issue #1500 <https://github.com/onaio/onadata/issues/1500>`_
  [lincmba]

1.15.0 (2018-10-10)
-------------------

- Submission Reviews
  `Issue #1428 <https://github.com/onaio/onadata/issues/1428>`_
  [DavisRayM, lincmba, moshthepitt]

- Track password edits.
  `Issue #1454 <https://github.com/onaio/onadata/issues/1453>`_
  [lincmba]

1.14.6 (2018-09-03)
-------------------

- Revert Track password edits.
  `Issue #1456 <https://github.com/onaio/onadata/pull/1456>`_
  [lincmba]


1.14.6 (2018-09-03)
-------------------

- Track password edits.
  `Issue #1456 <https://github.com/onaio/onadata/pull/1456>`_
  [lincmba]

- Enable email verification for accounts created via API,
  `Issue #1442 <https://github.com/onaio/onadata/pull/1442>`_
  [ivermac]

- Raise Validation Error when merging forms if there is a PyXFormError
  exception raised.
  `Issue #1153 <https://github.com/onaio/onadata/issues/1153>`_
  [ukanga]

- Update requirements/s3.pip
  `Issue #1465 <https://github.com/onaio/onadata/pull/1465>`_
  [ukanga]


1.14.5 (2018-08-15)
-------------------

- Fix Image resize() function to use file object directly.
  `Issue #1439 <https://github.com/onaio/onadata/pull/1439>`_
  [wambere]

- CSV upload updates
  `Issue #1444 <https://github.com/onaio/onadata/pull/1444>`_
  [ukanga]

- Updated/upgraded packages


1.14.4 (2018-06-21)
-------------------

- Support exporting labels for selects in the data.
  `Issue 1427 <https://github.com/onaio/onadata/issues/1427>`_
  [ukanga]

- Handle UnreadablePostError exception in submissions..
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

- Return flow results response timestamp in rfc3339 format explicitly
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


