# -*- coding: utf-8 -*-
"""
Test CSV Exports
"""

import csv
import os

from django.core.files.storage import storages
from django.db.models.signals import post_save
from django.utils.dateparse import parse_datetime

from onadata.apps.logger.models import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models import DataDictionary, Export
from onadata.apps.viewer.models.data_dictionary import create_or_update_export_register
from onadata.libs.utils.export_tools import generate_export


class TestCsvExport(TestBase):
    """
    TestCSVExport class
    """

    def setUp(self):
        self._create_user_and_login()

        self.fixture_dir = os.path.join(self.this_directory, "fixtures", "csv_export")
        self._submission_time = parse_datetime("2013-02-18 15:54:01Z")
        self.options = {"extension": "csv"}
        self.xform = None
        # Disable signals
        post_save.disconnect(
            sender=DataDictionary, dispatch_uid="create_or_update_export_register"
        )

    def tearDown(self):
        # Reconnect signals
        post_save.connect(
            sender=DataDictionary,
            dispatch_uid="create_or_update_export_register",
            receiver=create_or_update_export_register,
        )

        super().tearDown()

    def test_csv_export_output(self):
        """
        Test CSV export output
        """
        path = os.path.join(self.fixture_dir, "tutorial_w_repeats.xlsx")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(self.fixture_dir, "tutorial_w_repeats.xml")
        self._make_submission(path, forced_submission_time=self._submission_time)
        # test csv

        export = generate_export(Export.CSV_EXPORT, self.xform, None, self.options)
        storage = storages["default"]
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, ".csv")
        test_file_path = os.path.join(self.fixture_dir, "tutorial_w_repeats.csv")
        with storage.open(export.filepath, "r") as csv_file:
            self._test_csv_files(csv_file, test_file_path)

    def test_csv_nested_repeat_output(self):
        """
        Test CSV export with nested repeats
        """
        path = os.path.join(self.fixture_dir, "double_repeat.xlsx")
        self._publish_xls_file(path)
        self.xform = XForm.objects.get(id_string="double_repeat")
        path = os.path.join(self.fixture_dir, "instance.xml")
        self._make_submission(path, forced_submission_time=self._submission_time)
        self.maxDiff = None
        data_dictionary = DataDictionary.objects.all()[0]
        xpaths = [
            "/data/bed_net[1]/member[1]/name",
            "/data/bed_net[1]/member[2]/name",
            "/data/bed_net[2]/member[1]/name",
            "/data/bed_net[2]/member[2]/name",
            "/data/meta/instanceID",
        ]
        self.assertEqual(data_dictionary.xpaths(repeat_iterations=2), xpaths)
        # test csv
        export = generate_export(Export.CSV_EXPORT, self.xform, None, self.options)
        storage = storages["default"]
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, ".csv")
        test_file_path = os.path.join(self.fixture_dir, "export.csv")
        with storage.open(export.filepath, "r") as csv_file:
            self._test_csv_files(csv_file, test_file_path)

    def test_dotted_fields_csv_export(self):
        """
        Test CSV export with dotted field names
        """
        path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "userone",
            "userone_with_dot_name_fields.xlsx",
        )
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "userone",
            "userone_with_dot_name_fields.xml",
        )
        self._make_submission(path, forced_submission_time=self._submission_time)
        # test csv
        self.options["id_string"] = "userone"
        export = generate_export(Export.CSV_EXPORT, self.xform, None, self.options)
        storage = storages["default"]
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, ".csv")
        test_file_path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "userone",
            "userone_with_dot_name_fields.csv",
        )
        with storage.open(export.filepath, "r") as csv_file:
            self._test_csv_files(csv_file, test_file_path)

    def test_csv_truncated_titles(self):
        """
        Test CSV export with removed_group_name = True
        """
        path = os.path.join(self.fixture_dir, "tutorial_w_repeats.xlsx")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(self.fixture_dir, "tutorial_w_repeats.xml")
        self._make_submission(path, forced_submission_time=self._submission_time)
        # test csv
        self.options["remove_group_name"] = True
        export = generate_export(Export.CSV_EXPORT, self.xform, None, self.options)
        storage = storages["default"]
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, ".csv")
        test_file_path = os.path.join(
            self.fixture_dir, "tutorial_w_repeats_truncate_titles.csv"
        )
        with storage.open(export.filepath, "r") as csv_file:
            self._test_csv_files(csv_file, test_file_path)

    def test_csv_repeat_with_note(self):
        """
        Test that note field in repeat is not in csv export
        """
        path = os.path.join(self.fixture_dir, "repeat_w_note.xlsx")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(self.fixture_dir, "repeat_w_note.xml")
        self._make_submission(path, forced_submission_time=self._submission_time)
        export = generate_export(Export.CSV_EXPORT, self.xform, None, self.options)
        storage = storages["default"]
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, ".csv")
        with storage.open(export.filepath, "r") as csv_file:
            reader = csv.reader(csv_file)
            rows = [row for row in reader]
            actual_headers = [h for h in rows[0]]
            expected_headers = [
                "chnum",
                "chrepeat[1]/chname",
                "chrepeat[2]/chname",
                "meta/instanceID",
                "_id",
                "_uuid",
                "_submission_time",
                "_date_modified",
                "_tags",
                "_notes",
                "_version",
                "_duration",
                "_submitted_by",
                "_total_media",
                "_media_count",
                "_media_all_received",
            ]
            self.assertEqual(sorted(expected_headers), sorted(actual_headers))

    def test_csv_repeat_with_selects(self):
        """
        Test that select one and select multiple in a repeat are exported correctly.
        """
        md = """
        | survey   |
        |          |
        |          | type                                | name               | label                            |
        |          | text                                | name               | 1. What is your name?            |
        |          | integer                             | age                | 2. How old are you?              |
        |          | image                               | picture            | 3. May I take your picture?      |
        |          | select one from yes_no              | has_children       | 4. Do you have any children?     |
        |          | begin repeat                        | children           | 5. Children                      |
        |          | text                                | childs_name        | 5.1 Childs name?                 |
        |          | integer                             | childs_age         | 5.2 Childs age?                  |
        |          | select one from yes_no              | child_is_nursing   | 5.3 Is the child nursing?        |
        |          | end repeat                          |                    |                                  |
        |          | geopoint                            | gps                | 6. Record your GPS coordinates.  |
        |          | select all that apply from browsers | web_browsers       | 7. What web browsers do you use? |
        | choices  |
        |          | list name                           | name               | label                            |
        |          | yes_no                              | 0                  | No                               |
        |          | yes_no                              | 1                  | Yes                              |
        |          | browsers                            | firefox            | Mozilla Firefox                  |
        |          | browsers                            | chrome             | Google Chrome                    |
        |          | browsers                            | ie                 | Internet Explorer                |
        |          | browsers                            | safari             | Safari                           |
        | settings |
        |          | form_id                             |
        |          | tutorial_w_repeats                  |
        """
        data_dictionary = self._publish_markdown(
            md, self.user, id_string="tutorial_w_repeats"
        )
        xform = XForm.objects.get(pk=data_dictionary.pk)
        path = os.path.join(self.fixture_dir, "tutorial_w_repeats_selects.xml")
        self._make_submission(path, forced_submission_time=self._submission_time)
        export = generate_export(Export.CSV_EXPORT, xform, None, self.options)
        storage = storages["default"]
        self.assertTrue(storage.exists(export.filepath))
        path, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, ".csv")
        with storage.open(export.filepath, "r") as csv_file:
            reader = csv.reader(csv_file)
            rows = [row for row in reader]
            actual_headers = [h for h in rows[0]]
            expected_headers = [
                "name",
                "age",
                "picture",
                "has_children",
                "children[1]/childs_name",
                "children[1]/childs_age",
                "children[1]/child_is_nursing",
                "children[2]/childs_name",
                "children[2]/childs_age",
                "children[2]/child_is_nursing",
                "gps",
                "web_browsers/chrome",
                "web_browsers/firefox",
                "web_browsers/ie",
                "web_browsers/safari",
                "meta/instanceID",
                "_id",
                "_uuid",
                "_submission_time",
                "_date_modified",
                "_tags",
                "_notes",
                "_version",
                "_duration",
                "_gps_altitude",
                "_gps_latitude",
                "_gps_longitude",
                "_gps_precision",
                "_submitted_by",
                "_total_media",
                "_media_count",
                "_media_all_received",
            ]
            self.assertEqual(sorted(expected_headers), sorted(actual_headers))
            self.assertEqual(
                rows[1][:20],
                [
                    "Bob",
                    "25",
                    "n/a",
                    "1",
                    "Tom",
                    "12",
                    "0",
                    "Dick",
                    "1",
                    "1",
                    "-1.2625621 36.7921711 0.0 20.0",
                    "-1.2625621",
                    "36.7921711",
                    "0.0",
                    "20.0",
                    "n/a",
                    "n/a",
                    "n/a",
                    "n/a",
                    "uuid:b31c6ac2-b8ca-4180-914f-c844fa10ed3b",
                ],
            )
