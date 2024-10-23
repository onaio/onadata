# -*- coding: utf-8 -*-
"""
Test CSVDataFrameBuilder
"""

import csv
import os
from builtins import chr, open
from tempfile import NamedTemporaryFile

from django.test.utils import override_settings
from django.utils.dateparse import parse_datetime

from onadata.apps.logger.models import DataView
from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import xform_instance_to_dict
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.common_tags import NA_REP
from onadata.libs.utils.csv_builder import (
    AbstractDataFrameBuilder,
    CSVDataFrameBuilder,
    get_prefix_from_xpath,
    remove_dups_from_list_maintain_order,
    write_to_csv,
)


def xls_filepath_from_fixture_name(fixture_name):
    """
    Return an xls file path at tests/fixtures/[fixture]/fixture.xls
    """
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "fixtures",
        fixture_name,
        fixture_name + ".xlsx",
    )


# pylint: disable=invalid-name
def xml_inst_filepath_from_fixture_name(fixture_name, instance_name):
    """
    Returns the path to a fixture given fixture_name and instance_name.
    """
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "fixtures",
        fixture_name,
        "instances",
        fixture_name + "_" + instance_name + ".xml",
    )


class TestCSVDataFrameBuilder(TestBase):
    """
    CSVDataFrameBuilder test class
    """

    def setUp(self):
        self._create_user_and_login()
        self._submission_time = parse_datetime("2013-02-18 15:54:01Z")

    def _publish_xls_fixture_set_xform(self, fixture):
        """
        Publish an xls file at tests/fixtures/[fixture]/fixture.xls
        """
        xls_file_path = xls_filepath_from_fixture_name(fixture)
        count = XForm.objects.count()
        self._publish_xls_file(xls_file_path)
        self.assertEqual(XForm.objects.count(), count + 1)
        # pylint: disable=attribute-defined-outside-init
        self.xform = XForm.objects.all().reverse()[0]

    def _submit_fixture_instance(self, fixture, instance, submission_time=None):
        """
        Submit an instance at
        tests/fixtures/[fixture]/instances/[fixture]_[instance].xml
        """
        xml_submission_file_path = xml_inst_filepath_from_fixture_name(
            fixture, instance
        )
        self._make_submission(
            xml_submission_file_path, forced_submission_time=submission_time
        )
        self.assertEqual(self.response.status_code, 201)

    def _publish_single_level_repeat_form(self):
        self._publish_xls_fixture_set_xform("new_repeats")
        # pylint: disable=attribute-defined-outside-init
        self.survey_name = "new_repeats"

    def _publish_nested_repeats_form(self):
        self._publish_xls_fixture_set_xform("nested_repeats")
        # pylint: disable=attribute-defined-outside-init
        self.survey_name = "nested_repeats"

    def _publish_grouped_gps_form(self):
        self._publish_xls_fixture_set_xform("grouped_gps")
        # pylint: disable=attribute-defined-outside-init
        self.survey_name = "grouped_gps"

    def _csv_data_for_dataframe(self):
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        return [d for d in csv_df_builder._format_for_dataframe(cursor)]

    def test_csv_dataframe_export_to(self):
        """
        Test CSVDataFrameBuilder.export_to().
        """
        self._publish_nested_repeats_form()
        self._submit_fixture_instance(
            "nested_repeats", "01", submission_time=self._submission_time
        )
        self._submit_fixture_instance(
            "nested_repeats", "02", submission_time=self._submission_time
        )

        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_fixture_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures",
            "nested_repeats",
            "nested_repeats.csv",
        )
        temp_file.close()
        with open(temp_file.name) as csv_file:
            self._test_csv_files(csv_file, csv_fixture_path)
        os.unlink(temp_file.name)

    # pylint: disable=invalid-name
    def test_csv_columns_for_gps_within_groups(self):
        """
        Test CSV columns for GPS fields within groups.
        """
        self._publish_grouped_gps_form()
        self._submit_fixture_instance("grouped_gps", "01")
        data = self._csv_data_for_dataframe()
        columns = list(data[0])
        expected_columns = (
            [
                "gps_group/gps",
                "gps_group/_gps_latitude",
                "gps_group/_gps_longitude",
                "gps_group/_gps_altitude",
                "gps_group/_gps_precision",
                "web_browsers/firefox",
                "web_browsers/chrome",
                "web_browsers/ie",
                "web_browsers/safari",
                "_xform_id",
            ]
            + AbstractDataFrameBuilder.ADDITIONAL_COLUMNS
            + AbstractDataFrameBuilder.IGNORED_COLUMNS
        )
        try:
            expected_columns.remove("_deleted_at")
            expected_columns.remove("_review_status")
            expected_columns.remove("_review_comment")
            expected_columns.remove("_review_date")
        except ValueError:
            pass
        self.maxDiff = None
        self.assertEqual(sorted(expected_columns), sorted(columns))

    def test_format_mongo_data_for_csv(self):
        """
        Test format mongo data for CSV.
        """
        self.maxDiff = None
        self._publish_single_level_repeat_form()
        self._submit_fixture_instance("new_repeats", "01")
        data_0 = self._csv_data_for_dataframe()[0]
        # remove AbstractDataFrameBuilder.INTERNAL_FIELDS
        for key in AbstractDataFrameBuilder.IGNORED_COLUMNS:
            if key in data_0:
                data_0.pop(key)
        for key in AbstractDataFrameBuilder.ADDITIONAL_COLUMNS:
            if key in data_0:
                data_0.pop(key)
        expected_data_0 = {
            "gps": "-1.2627557 36.7926442 0.0 30.0",
            "_gps_latitude": "-1.2627557",
            "_gps_longitude": "36.7926442",
            "_gps_altitude": "0.0",
            "_gps_precision": "30.0",
            "kids/has_kids": "1",
            "info/age": 80,
            "kids/kids_details[1]/kids_name": "Abel",
            "kids/kids_details[1]/kids_age": 50,
            "kids/kids_details[2]/kids_name": "Cain",
            "kids/kids_details[2]/kids_age": 76,
            "web_browsers/chrome": True,
            "web_browsers/ie": True,
            "web_browsers/safari": False,
            "web_browsers/firefox": False,
            "info/name": "Adam",
            "_xform_id": self.xform.pk,
        }
        self.assertEqual(expected_data_0, data_0)

    def test_split_select_multiples(self):
        """
        Test select multiples choices are split.
        """
        self._publish_nested_repeats_form()
        self._submit_fixture_instance("nested_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        # pylint: disable=protected-access
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        record = cursor[0]
        select_multiples = CSVDataFrameBuilder._collect_select_multiples(self.xform)
        result = CSVDataFrameBuilder._split_select_multiples(record, select_multiples)
        expected_result = {
            "web_browsers/ie": True,
            "web_browsers/safari": True,
            "web_browsers/firefox": False,
            "web_browsers/chrome": False,
        }
        # build a new dictionary only composed of the keys we want to use in
        # the comparison
        result = dict(
            [(key, result[key]) for key in list(result) if key in list(expected_result)]
        )
        self.assertEqual(expected_result, result)
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, binary_select_multiples=True
        )
        # pylint: disable=protected-access
        result = csv_df_builder._split_select_multiples(record, select_multiples)
        expected_result = {
            "web_browsers/ie": 1,
            "web_browsers/safari": 1,
            "web_browsers/firefox": 0,
            "web_browsers/chrome": 0,
        }
        # build a new dictionary only composed of the keys we want to use in
        # the comparison
        result = dict(
            [(key, result[key]) for key in list(result) if key in list(expected_result)]
        )
        self.assertEqual(expected_result, result)

    def test_split_select_multiples_values(self):
        """
        Test select multiples choices are split and their values as the data.
        """
        self._publish_nested_repeats_form()
        self._submit_fixture_instance("nested_repeats", "01")
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        record = cursor[0]
        select_multiples = CSVDataFrameBuilder._collect_select_multiples(self.xform)
        result = CSVDataFrameBuilder._split_select_multiples(
            record, select_multiples, value_select_multiples=True
        )
        expected_result = {
            "web_browsers/ie": "ie",
            "web_browsers/safari": "safari",
            "web_browsers/firefox": None,
            "web_browsers/chrome": None,
        }
        # build a new dictionary only composed of the keys we want to use in
        # the comparison
        result = dict(
            [(key, result[key]) for key in list(result) if key in list(expected_result)]
        )
        self.assertEqual(expected_result, result)

    # pylint: disable=invalid-name
    def test_split_select_multiples_within_repeats(self):
        """
        Test select multiples choices are split within repeats in CSV exports.
        """
        self.maxDiff = None
        record = {
            "name": "Tom",
            "age": 23,
            "browser_use": [
                {"browser_use/year": "2010", "browser_use/browsers": "firefox safari"},
                {"browser_use/year": "2011", "browser_use/browsers": "firefox chrome"},
            ],
        }  # yapf: disable
        expected_result = {
            "name": "Tom",
            "age": 23,
            "browser_use": [
                {
                    "browser_use/year": "2010",
                    "browser_use/browsers/firefox": True,
                    "browser_use/browsers/safari": True,
                    "browser_use/browsers/ie": False,
                    "browser_use/browsers/chrome": False,
                },
                {
                    "browser_use/year": "2011",
                    "browser_use/browsers/firefox": True,
                    "browser_use/browsers/safari": False,
                    "browser_use/browsers/ie": False,
                    "browser_use/browsers/chrome": True,
                },
            ],
        }  # yapf: disable
        select_multiples = {
            "browser_use/browsers": [
                ("browser_use/browsers/firefox", "firefox", "Firefox"),
                ("browser_use/browsers/safari", "safari", "Safari"),
                ("browser_use/browsers/ie", "ie", "Internet Explorer"),
                ("browser_use/browsers/chrome", "chrome", "Google Chrome"),
            ]
        }
        # pylint: disable=protected-access
        result = CSVDataFrameBuilder._split_select_multiples(record, select_multiples)
        self.assertEqual(expected_result, result)

    def test_split_gps_fields(self):
        """
        Test GPS fields data are split into latitude, longitude, altitude, and
        precision segments.
        """
        record = {"gps": "5 6 7 8"}
        gps_fields = ["gps"]
        expected_result = {
            "gps": "5 6 7 8",
            "_gps_latitude": "5",
            "_gps_longitude": "6",
            "_gps_altitude": "7",
            "_gps_precision": "8",
        }
        # pylint: disable=protected-access
        AbstractDataFrameBuilder._split_gps_fields(record, gps_fields)
        self.assertEqual(expected_result, record)

    # pylint: disable=invalid-name
    def test_split_gps_fields_within_repeats(self):
        """
        Test GPS fields data is split within repeats.
        """
        record = {
            "a_repeat": [{"a_repeat/gps": "1 2 3 4"}, {"a_repeat/gps": "5 6 7 8"}]
        }
        gps_fields = ["a_repeat/gps"]
        expected_result = {
            "a_repeat": [
                {
                    "a_repeat/gps": "1 2 3 4",
                    "a_repeat/_gps_latitude": "1",
                    "a_repeat/_gps_longitude": "2",
                    "a_repeat/_gps_altitude": "3",
                    "a_repeat/_gps_precision": "4",
                },
                {
                    "a_repeat/gps": "5 6 7 8",
                    "a_repeat/_gps_latitude": "5",
                    "a_repeat/_gps_longitude": "6",
                    "a_repeat/_gps_altitude": "7",
                    "a_repeat/_gps_precision": "8",
                },
            ]
        }
        # pylint: disable=protected-access
        AbstractDataFrameBuilder._split_gps_fields(record, gps_fields)
        self.assertEqual(expected_result, record)

    def test_unicode_export(self):
        """
        Test write_to_csv() with unicode characters.
        """
        unicode_char = chr(40960)
        # fake data
        data = [{"key": unicode_char}]
        columns = ["key"]
        # test csv
        passed = False
        temp_file = NamedTemporaryFile(suffix=".csv")
        write_to_csv(temp_file.name, data, columns)
        try:
            write_to_csv(temp_file.name, data, columns)
            passed = True
        except UnicodeEncodeError:
            pass
        finally:
            temp_file.close()
        temp_file.close()
        self.assertTrue(passed)

    # pylint: disable=invalid-name
    def test_repeat_child_name_matches_repeat(self):
        """
        ParsedInstance.to_dict creates a list within a repeat if a child has
        the same name as the repeat. This test makes sure that doesnt happen
        """
        self.maxDiff = None
        fixture = "repeat_child_name_matches_repeat"
        # publish form so we have a dd to pass to xform inst. parser
        self._publish_xls_fixture_set_xform(fixture)
        submission_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures",
            fixture,
            fixture + ".xml",
        )
        # get submission xml str
        with open(submission_path, "r") as f:
            xml_str = f.read()
        xform_instance_dict = xform_instance_to_dict(xml_str, self.xform)
        expected_dict = {
            "test_item_name_matches_repeat": {
                "formhub": {"uuid": "c911d71ce1ac48478e5f8bac99addc4e"},
                "gps": [
                    {"info": "Yo", "gps": "-1.2625149 36.7924478 0.0 30.0"},
                    {"info": "What", "gps": "-1.2625072 36.7924328 0.0 30.0"},
                ],
            }
        }
        self.assertEqual(xform_instance_dict, expected_dict)

    # pylint: disable=invalid-name
    def test_remove_dups_from_list_maintain_order(self):
        """
        Test remove_dups_from_list_maintain_order().
        """
        list_with_dups = ["a", "z", "b", "y", "c", "b", "x"]
        result = remove_dups_from_list_maintain_order(list_with_dups)
        expected_result = ["a", "z", "b", "y", "c", "x"]
        self.assertEqual(result, expected_result)

    def test_get_prefix_from_xpath(self):
        """
        Test get_prefix_from_xpath(xpath) function.
        """
        xpath = "parent/child/grandhild"
        prefix = get_prefix_from_xpath(xpath)
        self.assertEqual(prefix, "parent/child/")
        xpath = "parent/child"
        prefix = get_prefix_from_xpath(xpath)
        self.assertEqual(prefix, "parent/")
        xpath = "parent"
        prefix = get_prefix_from_xpath(xpath)
        self.assertTrue(prefix is None)

    def test_csv_export(self):
        """
        Test CSV export.
        """
        self._publish_single_level_repeat_form()
        # submit 7 instances
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        for _ in range(2):
            self._submit_fixture_instance("new_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 7)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all()
            .order_by("id")
            .order_by("id")
            .values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 17 + len(csv_df_builder.extra_columns))
        rows = []
        for row in csv_reader:
            rows.append(row)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[4][5], NA_REP)
        # close and delete file
        csv_file.close()

    def test_windows_excel_compatible_csv_export(self):
        """
        Test window excel compatible CSV export.
        """
        self._publish_single_level_repeat_form()
        # submit 7 instances
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        for _ in range(2):
            self._submit_fixture_instance("new_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_images=False,
            win_excel_utf8=True,
        )
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 7)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 17 + len(csv_df_builder.extra_columns))
        self.assertEqual(b"\xef\xbb\xbfname", header[0].encode("utf-8"))
        # close and delete file
        csv_file.close()
        os.unlink(temp_file.name)

    def test_csv_column_indices_in_groups_within_repeats(self):
        """
        Test CSV column indices in groups within repeats.
        """
        self._publish_xls_fixture_set_xform("groups_in_repeats")
        self._submit_fixture_instance("groups_in_repeats", "01")
        self.xform.get_keys()
        data_0 = self._csv_data_for_dataframe()[0]
        # remove dynamic fields
        ignore_list = [
            "_uuid",
            "meta/instanceID",
            "formhub/uuid",
            "_submission_time",
            "_id",
            "_bamboo_dataset_id",
            "_date_modified",
        ]
        for item in ignore_list:
            data_0.pop(item)
        expected_data_0 = {
            "_xform_id_string": "groups_in_repeats",
            "_xform_id": self.xform.pk,
            "_status": "submitted_via_web",
            "_tags": "",
            "_notes": "",
            "_version": self.xform.version,
            "_submitted_by": "bob",
            "name": "Abe",
            "age": 88,
            "has_children": "1",
            "children[1]/childs_info/name": "Cain",
            "children[2]/childs_info/name": "Abel",
            "children[1]/childs_info/age": 56,
            "children[2]/childs_info/age": 48,
            "children[1]/immunization/immunization_received/polio_1": True,
            "children[1]/immunization/immunization_received/polio_2": False,
            "children[2]/immunization/immunization_received/polio_1": True,
            "children[2]/immunization/immunization_received/polio_2": True,
            "web_browsers/chrome": True,
            "web_browsers/firefox": False,
            "web_browsers/ie": False,
            "web_browsers/safari": False,
            "gps": "-1.2626156 36.7923571 0.0 30.0",
            "_geolocation": [-1.2626156, 36.7923571],
            "_duration": "",
            "_edited": False,
            "_gps_latitude": "-1.2626156",
            "_gps_longitude": "36.7923571",
            "_gps_altitude": "0.0",
            "_gps_precision": "30.0",
            "_attachments": [],
            "_total_media": 0,
            "_media_count": 0,
            "_media_all_received": True,
        }
        self.maxDiff = None
        self.assertEqual(data_0, expected_data_0)

    def test_csv_export_remove_group_name(self):
        """
        Test CSV export with remove_group_name option.
        """
        self._publish_single_level_repeat_form()
        # submit 7 instances
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        for _ in range(2):
            self._submit_fixture_instance("new_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_images=False,
            include_reviews=True,
        )
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 7)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 17 + len(csv_df_builder.extra_columns))
        expected_header = [
            "name",
            "age",
            "has_kids",
            "kids_name",
            "kids_age",
            "kids_name",
            "kids_age",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
            "web_browsers/ie",
            "web_browsers/safari",
            "instanceID",
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
            "_review_status",
            "_review_comment",
            "_review_date",
        ]
        self.assertEqual(expected_header, header)
        rows = []
        for row in csv_reader:
            rows.append(row)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[4][5], NA_REP)
        # close and delete file
        csv_file.close()
        os.unlink(temp_file.name)

    def test_remove_group_name_for_gps_within_groups(self):
        """
        Test gps CSV export with remove_group_name option.
        """
        self._publish_grouped_gps_form()
        self._submit_fixture_instance("grouped_gps", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_images=False,
            include_reviews=True,
        )
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 1)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 10 + len(csv_df_builder.extra_columns))
        expected_header = [
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
            "web_browsers/ie",
            "web_browsers/safari",
            "instanceID",
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
            "_review_status",
            "_review_comment",
            "_review_date",
        ]
        self.assertEqual(expected_header, header)
        rows = []
        for row in csv_reader:
            rows.append(row)
        self.assertEqual(len(rows), 1)
        # close and delete file
        csv_file.close()
        os.unlink(temp_file.name)

    def test_csv_export_with_labels(self):
        """
        Test CSV export with labels.
        """
        self._publish_single_level_repeat_form()
        # submit 7 instances
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        for _ in range(2):
            self._submit_fixture_instance("new_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_labels=True,
            include_reviews=True,
        )
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 7)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 17 + len(csv_df_builder.extra_columns))
        expected_header = [
            "name",
            "age",
            "has_kids",
            "kids_name",
            "kids_age",
            "kids_name",
            "kids_age",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
            "web_browsers/ie",
            "web_browsers/safari",
            "instanceID",
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
            "_review_status",
            "_review_comment",
            "_review_date",
        ]
        self.assertEqual(expected_header, header)
        labels = next(csv_reader)
        self.assertEqual(len(labels), 17 + len(csv_df_builder.extra_columns))
        expected_labels = [
            "Name",
            "age",
            "Do you have kids?",
            "Kids Name",
            "Kids Age",
            "Kids Name",
            "Kids Age",
            "5. Record your GPS coordinates.",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/Mozilla Firefox",
            "web_browsers/Google Chrome",
            "web_browsers/Internet Explorer",
            "web_browsers/Safari",
            "instanceID",
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
            "_review_status",
            "_review_comment",
            "_review_date",
        ]
        self.assertEqual(expected_labels, labels)
        rows = []
        for row in csv_reader:
            rows.append(row)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[4][5], NA_REP)
        # close and delete file
        csv_file.close()
        os.unlink(temp_file.name)

    def test_csv_export_with_labels_only(self):
        """
        Test CSV export with labels only.
        """
        self._publish_single_level_repeat_form()
        # submit 7 instances
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        for _ in range(2):
            self._submit_fixture_instance("new_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_labels_only=True,
            include_reviews=True,
        )
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 7)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        labels = next(csv_reader)
        self.assertEqual(len(labels), 17 + len(csv_df_builder.extra_columns))
        expected_labels = [
            "Name",
            "age",
            "Do you have kids?",
            "Kids Name",
            "Kids Age",
            "Kids Name",
            "Kids Age",
            "5. Record your GPS coordinates.",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/Mozilla Firefox",
            "web_browsers/Google Chrome",
            "web_browsers/Internet Explorer",
            "web_browsers/Safari",
            "instanceID",
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
            "_review_status",
            "_review_comment",
            "_review_date",
        ]
        self.assertEqual(expected_labels, labels)
        rows = []
        for row in csv_reader:
            rows.append(row)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[4][5], NA_REP)
        # close and delete file
        csv_file.close()
        os.unlink(temp_file.name)

    def test_no_split_select_multiples(self):
        """
        Test select multiples are not split within repeats.
        """
        md_xform = """
        | survey |
        |        | type                     | name         | label        |
        |        | text                     | name         | Name         |
        |        | integer                  | age          | Age          |
        |        | begin repeat             | browser_use  | Browser Use  |
        |        | integer                  | year         | Year         |
        |        | select_multiple browsers | browsers     | Browsers     |
        |        | end repeat               |              |              |

        | choices |
        |         | list name | name    | label             |
        |         | browsers  | firefox | Firefox           |
        |         | browsers  | chrome  | Chrome            |
        |         | browsers  | ie      | Internet Explorer |
        |         | browsers  | safari  | Safari            |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [
            {
                "name": "Tom",
                "age": 23,
                "browser_use": [
                    {
                        "browser_use/year": "2010",
                        "browser_use/browsers": "firefox safari",
                    },
                    {
                        "browser_use/year": "2011",
                        "browser_use/browsers": "firefox chrome",
                    },
                ],
            }
        ]  # yapf: disable

        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [
            {
                "name": "Tom",
                "age": 23,
                "browser_use[1]/year": "2010",
                "browser_use[1]/browsers": "firefox safari",
                "browser_use[2]/year": "2011",
                "browser_use[2]/browsers": "firefox chrome",
            }
        ]
        self.maxDiff = None
        self.assertEqual(expected_result, result)

    @override_settings(EXTRA_COLUMNS=["_xform_id"])
    def test_csv_export_extra_columns(self):
        """
        Test CSV export EXTRA_COLUMNS
        """
        self._publish_single_level_repeat_form()
        # submit 7 instances
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        for _ in range(2):
            self._submit_fixture_instance("new_repeats", "01")
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_labels=True,
            include_reviews=True,
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 17 + len(csv_df_builder.extra_columns))
        expected_header = [
            "name",
            "age",
            "has_kids",
            "kids_name",
            "kids_age",
            "kids_name",
            "kids_age",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
            "web_browsers/ie",
            "web_browsers/safari",
            "instanceID",
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
            "_xform_id",
            "_review_status",
            "_review_comment",
            "_review_date",
        ]
        self.assertEqual(expected_header, header)
        # close and delete file
        csv_file.close()
        os.unlink(temp_file.name)

        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            remove_group_name=True,
            include_labels=True,
            include_reviews=True,
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        self.assertEqual(len(header), 17 + len(csv_df_builder.extra_columns))
        self.assertEqual(expected_header, header)
        csv_file.close()
        os.unlink(temp_file.name)

    def test_index_tag_replacement(self):
        """
        Test that the default index tags are correctly replaced by an
        underscore
        """
        self._publish_xls_fixture_set_xform("groups_in_repeats")
        self._submit_fixture_instance("groups_in_repeats", "01")
        self.xform.get_keys()

        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            self.xform.id_string,
            include_images=False,
            index_tags=("_", "_"),
        )
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        result = [d for d in csv_df_builder._format_for_dataframe(cursor)][0]
        # remove dynamic fields
        ignore_list = [
            "_uuid",
            "meta/instanceID",
            "formhub/uuid",
            "_submission_time",
            "_id",
            "_bamboo_dataset_id",
            "_date_modified",
        ]
        for item in ignore_list:
            result.pop(item)
        expected_result = {
            "_xform_id_string": "groups_in_repeats",
            "_xform_id": self.xform.pk,
            "_status": "submitted_via_web",
            "_tags": "",
            "_notes": "",
            "_version": self.xform.version,
            "_submitted_by": "bob",
            "name": "Abe",
            "age": 88,
            "has_children": "1",
            "children_1_/childs_info/name": "Cain",
            "children_2_/childs_info/name": "Abel",
            "children_1_/childs_info/age": 56,
            "children_2_/childs_info/age": 48,
            "children_1_/immunization/immunization_received/polio_1": True,
            "children_1_/immunization/immunization_received/polio_2": False,
            "children_2_/immunization/immunization_received/polio_1": True,
            "children_2_/immunization/immunization_received/polio_2": True,
            "web_browsers/chrome": True,
            "web_browsers/firefox": False,
            "web_browsers/ie": False,
            "web_browsers/safari": False,
            "gps": "-1.2626156 36.7923571 0.0 30.0",
            "_geolocation": [-1.2626156, 36.7923571],
            "_duration": "",
            "_edited": False,
            "_gps_latitude": "-1.2626156",
            "_gps_longitude": "36.7923571",
            "_gps_altitude": "0.0",
            "_gps_precision": "30.0",
            "_attachments": [],
            "_total_media": 0,
            "_media_count": 0,
            "_media_all_received": True,
        }

        self.maxDiff = None
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_multi_language(self):
        """
        Test show_choice_labels=true for select one questions - multi language
        form.
        """
        md_xform = """
        | survey  |
        |         | type              | name  | label:English | label:French |
        |         | text              | name  | Name          | Prénom       |
        |         | integer           | age   | Age           | Âge          |
        |         | select one fruits | fruit | Fruit         | Fruit        |
        |         |                   |       |               |              |
        | choices | list name         | name  | label:English | label:French |
        |         | fruits            | 1     | Mango         | Mangue       |
        |         | fruits            | 2     | Orange        | Orange       |
        |         | fruits            | 3     | Apple         | Pomme        |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1"}]  # yapf: disable
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
            language="French",
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [{"name": "Maria", "age": 25, "fruit": "Mangue"}]
        self.maxDiff = None
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_multi_language_1(self):
        """
        Test show_choice_labels=true for select one questions - multi language
        form selected language.
        """
        md_xform = """
        | survey  |
        |         | type              | name  | label:English | label:French |
        |         | text              | name  | Name          | Prénom       |
        |         | integer           | age   | Age           | Âge          |
        |         | select one fruits | fruit | Fruit         | Fruit        |
        |         |                   |       |               |              |
        | choices | list name         | name  | label:English | label:French |
        |         | fruits            | 1     | Mango         | Mangue       |
        |         | fruits            | 2     | Orange        | Orange       |
        |         | fruits            | 3     | Apple         | Pomme        |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1"}]  # yapf: disable
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
            language="English",
        )
        # pylint: disable=protected-access
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [{"name": "Maria", "age": 25, "fruit": "Mango"}]
        self.maxDiff = None
        self.assertEqual(expected_result, result)

    def test_show_choice_labels(self):
        """
        Test show_choice_labels=true for select one questions.
        """
        md_xform = """
        | survey  |
        |         | type              | name  | label  |
        |         | text              | name  | Name   |
        |         | integer           | age   | Age    |
        |         | select one fruits | fruit | Fruit  |
        |         |                   |       |        |
        | choices | list name         | name  | label  |
        |         | fruits            | 1     | Mango  |
        |         | fruits            | 2     | Orange |
        |         | fruits            | 3     | Apple  |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1"}]  # yapf: disable
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [{"name": "Maria", "age": 25, "fruit": "Mango"}]
        self.maxDiff = None
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_select_multiple(self):
        """
        Test show_choice_labels=true for select multiple questions.
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label  |
        |         | text                   | name  | Name   |
        |         | integer                | age   | Age    |
        |         | select_multiple fruits | fruit | Fruit  |
        |         |                        |       |        |
        | choices | list name              | name  | label  |
        |         | fruits                 | 1     | Mango  |
        |         | fruits                 | 2     | Orange |
        |         | fruits                 | 3     | Apple  |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]  # yapf: disable
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [{"name": "Maria", "age": 25, "fruit": "Mango Orange"}]
        self.maxDiff = None
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_select_multiple_language(self):
        """
        Test show_choice_labels=true for select multiple questions - multi
        language form.
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label:Eng  | label:Fr |
        |         | text                   | name  | Name       | Prénom   |
        |         | integer                | age   | Age        | Âge      |
        |         | select_multiple fruits | fruit | Fruit      | Fruit    |
        |         |                        |       |            |          |
        | choices | list name              | name  | label:Eng  | label:Fr |
        |         | fruits                 | 1     | Mango      | Mangue   |
        |         | fruits                 | 2     | Orange     | Orange   |
        |         | fruits                 | 3     | Apple      | Pomme    |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]  # yapf: disable
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
            language="Fr",
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [{"name": "Maria", "age": 25, "fruit": "Mangue Orange"}]
        self.maxDiff = None
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_select_multiple_1(self):
        """
        Test show_choice_labels=true, split_select_multiples=true and
        value_select_multiples=true for select multiple questions.
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label  |
        |         | text                   | name  | Name   |
        |         | integer                | age   | Age    |
        |         | select_multiple fruits | fruit | Fruit  |
        |         |                        |       |        |
        | choices | list name              | name  | label  |
        |         | fruits                 | 1     | Mango  |
        |         | fruits                 | 2     | Orange |
        |         | fruits                 | 3     | Apple  |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]  # yapf: disable
        # Split Select multiples, value_select_multiples is True
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=True,
            value_select_multiples=True,
            include_images=False,
            show_choice_labels=True,
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [
            {
                "name": "Maria",
                "age": 25,
                "fruit/Mango": "Mango",
                "fruit/Orange": "Orange",
                "fruit/Apple": None,
            }
        ]
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_select_multiple_1_language(self):
        """
        Test show_choice_labels=true, split_select_multiples=true and
        value_select_multiples=true for select multiple questions - multi
        language form.
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label:Eng  | label:Fr |
        |         | text                   | name  | Name       | Prénom   |
        |         | integer                | age   | Age        | Âge      |
        |         | select_multiple fruits | fruit | Fruit      | Fruit    |
        |         |                        |       |            |          |
        | choices | list name              | name  | label:Eng  | label:Fr |
        |         | fruits                 | 1     | Mango      | Mangue   |
        |         | fruits                 | 2     | Orange     | Orange   |
        |         | fruits                 | 3     | Apple      | Pomme    |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]  # yapf: disable
        # Split Select multiples, value_select_multiples is True
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=True,
            value_select_multiples=True,
            include_images=False,
            show_choice_labels=True,
            language="Fr",
        )
        result = [k for k in csv_df_builder._format_for_dataframe(cursor)]
        expected_result = [
            {
                "name": "Maria",
                "age": 25,
                "fruit/Mangue": "Mangue",
                "fruit/Orange": "Orange",
                "fruit/Pomme": None,
            }
        ]
        self.assertEqual(expected_result, result)

    def test_show_choice_labels_select_multiple_2(self):
        """
        Test show_choice_labels=true, split_select_multiples=true,
        binary_select_multiples=true for select multiple questions.
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label  |
        |         | text                   | name  | Name   |
        |         | integer                | age   | Age    |
        |         | select_multiple fruits | fruit | Fruit  |
        |         |                        |       |        |
        | choices | list name              | name  | label  |
        |         | fruits                 | 1     | Mango  |
        |         | fruits                 | 2     | Orange |
        |         | fruits                 | 3     | Apple  |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]  # yapf: disable
        # Split Select multiples, binary_select_multiples is True
        csv_df_builder_1 = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=True,
            binary_select_multiples=True,
            include_images=False,
            show_choice_labels=True,
        )
        result = [k for k in csv_df_builder_1._format_for_dataframe(cursor)]
        expected_result = [
            {
                "name": "Maria",
                "age": 25,
                "fruit/Mango": 1,
                "fruit/Orange": 1,
                "fruit/Apple": 0,
            }
        ]
        self.assertEqual(expected_result, result)

    def test_export_data_for_xforms_without_submissions(self):
        """
        Test xform schema for form with no submission
        is successfully exported
        """
        fixture = "new_repeats"
        # publish form so we have a dd
        self._publish_xls_fixture_set_xform(fixture)

        # Confirm form has not submissions so far
        self.assertEqual(self.xform.instances.count(), 0)
        # Generate csv export for form
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)

        expected_header = [
            "info/name",
            "info/age",
            "kids/has_kids",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
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
            "_submitted_by",
            "_total_media",
            "_media_count",
            "_media_all_received",
        ]
        # Test form headers are present on exported csv file.
        self.assertEqual(header, expected_header)

        csv_file.close()

    def test_export_data_for_xforms_with_newer_submissions(self):
        """
        Test xform schema for form with no submission
        is successfully exported
        """
        fixture = "new_repeats"
        # publish form so we have a dd
        self._publish_xls_fixture_set_xform(fixture)

        # Confirm form has not submissions so far
        self.assertEqual(self.xform.instances.count(), 0)
        # Generate csv export for form
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)

        expected_header = [
            "info/name",
            "info/age",
            "kids/has_kids",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
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
            "_submitted_by",
            "_total_media",
            "_media_count",
            "_media_all_received",
        ]
        # Test form headers are present on exported csv file.
        self.assertEqual(header, expected_header)

        # make sibmissions to xform after export was generated
        for _ in range(4):
            self._submit_fixture_instance("new_repeats", "01")
        self._submit_fixture_instance("new_repeats", "02")
        # pylint: disable=protected-access
        record_count = self.xform.instances.count()
        self.assertEqual(record_count, 5)
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        cursor = (
            self.xform.instances.all().order_by("id").values_list("json", flat=True)
        )
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        newer_header = next(csv_reader)
        expected_headers = [
            "info/name",
            "info/age",
            "kids/has_kids",
            "kids/kids_details[1]/kids_name",
            "kids/kids_details[1]/kids_age",
            "kids/kids_details[2]/kids_name",
            "kids/kids_details[2]/kids_age",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
            "web_browsers/firefox",
            "web_browsers/chrome",
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
            "_submitted_by",
            "_total_media",
            "_media_count",
            "_media_all_received",
        ]

        # Test export headers are recreated with repeat data.
        self.assertEqual(newer_header, expected_headers)

        self.assertEqual(len(header), 13 + len(csv_df_builder.extra_columns))
        rows = []
        for row in csv_reader:
            rows.append(row)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[4][5], NA_REP)

        # close and delete file
        csv_file.close()

    def test_show_choice_labels_select_multiple_3(self):
        """
        Test show_choice_labels=true, split_select_multiples=true,
        binary_select_multiples=false for select multiple questions.
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label  |
        |         | text                   | name  | Name   |
        |         | integer                | age   | Age    |
        |         | select_multiple fruits | fruit | Fruit  |
        |         |                        |       |        |
        | choices | list name              | name  | label  |
        |         | fruits                 | 1     | Mango  |
        |         | fruits                 | 2     | Orange |
        |         | fruits                 | 3     | Apple  |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]  # yapf: disable
        # Split Select multiples, binary_select_multiples is True
        csv_df_builder_1 = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=True,
            binary_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
        )
        result = [k for k in csv_df_builder_1._format_for_dataframe(cursor)]
        expected_result = [
            {
                "name": "Maria",
                "age": 25,
                "fruit/Mango": True,
                "fruit/Orange": True,
                "fruit/Apple": 0,
            }
        ]
        self.assertEqual(expected_result, result)

    def test_multiple_repeats_column_order(self):
        """Test the order of the columns in a multiple repeats form export"""
        md_xform = """
        | survey  |
        |         | type                 | name          | label       | repeat_count | relevant                   |
        |         | select_multiple food | food          | Food:       |              |                            |
        |         | integer              | no_food       | No. Food    |              |                            |
        |         | begin repeat         | food_repeat   | Food Repeat | ${no_food}   |                            |
        |         | select_multiple food | food_group    | Food:       |              |                            |
        |         | end repeat           |               |             |              |                            |
        |         | integer              | no_food_2     | No. Food    |              |                            |
        |         | begin repeat         | food_repeat_2 | Food Repeat | ${no_food_2} | selected(${food}, 'Apple') |
        |         | select_multiple food | food_group_2  | Food:       |              |                            |
        |         | end repeat           |               |             |              |                            |
        |         | geopoint             | gps           | GPS         |              |                            |
        |         |                      |               |             |              |                            |
        | choices | list name            | name          | label       |              |                            |
        |         | food                 | Apple         | Apple       |              |                            |
        |         | food                 | Orange        | Orange      |              |                            |
        |         | food                 | Banana        | Banana      |              |                            |
        |         | food                 | Pizza         | Pizza       |              |                            |
        |         | food                 | Lasgna        | Lasgna      |              |                            |
        |         | food                 | Cake          | Cake        |              |                            |
        |         | food                 | Chocolate     | Chocolate   |              |                            |
        |         | food                 | Salad         | Salad       |              |                            |
        |         | food                 | Sandwich      | Sandwich    |              |                            |
        """  # noqa: E501
        self.xform = self._publish_markdown(md_xform, self.user, id_string="b")

        cursor = [
            {
                "food": "Orange",
                "no_food": 2,
                "food_repeat": [
                    {"food_repeat/food_group": "Banana"},
                    {"food_repeat/food_group": "Lasgna"},
                ],
            },
            {
                "food": "Apple",
                "no_food_2": 2,
                "food_repeat_2": [
                    {"food_repeat_2/food_group_2": "Cake"},
                    {"food_repeat_2/food_group_2": "Salad"},
                ],
            },
        ]
        expected_header = [
            "food/Apple",
            "food/Orange",
            "food/Banana",
            "food/Pizza",
            "food/Lasgna",
            "food/Cake",
            "food/Chocolate",
            "food/Salad",
            "food/Sandwich",
            "no_food",
            "food_repeat[1]/food_group/Apple",
            "food_repeat[1]/food_group/Orange",
            "food_repeat[1]/food_group/Banana",
            "food_repeat[1]/food_group/Pizza",
            "food_repeat[1]/food_group/Lasgna",
            "food_repeat[1]/food_group/Cake",
            "food_repeat[1]/food_group/Chocolate",
            "food_repeat[1]/food_group/Salad",
            "food_repeat[1]/food_group/Sandwich",
            "food_repeat[2]/food_group/Apple",
            "food_repeat[2]/food_group/Orange",
            "food_repeat[2]/food_group/Banana",
            "food_repeat[2]/food_group/Pizza",
            "food_repeat[2]/food_group/Lasgna",
            "food_repeat[2]/food_group/Cake",
            "food_repeat[2]/food_group/Chocolate",
            "food_repeat[2]/food_group/Salad",
            "food_repeat[2]/food_group/Sandwich",
            "no_food_2",
            "food_repeat_2[1]/food_group_2/Apple",
            "food_repeat_2[1]/food_group_2/Orange",
            "food_repeat_2[1]/food_group_2/Banana",
            "food_repeat_2[1]/food_group_2/Pizza",
            "food_repeat_2[1]/food_group_2/Lasgna",
            "food_repeat_2[1]/food_group_2/Cake",
            "food_repeat_2[1]/food_group_2/Chocolate",
            "food_repeat_2[1]/food_group_2/Salad",
            "food_repeat_2[1]/food_group_2/Sandwich",
            "food_repeat_2[2]/food_group_2/Apple",
            "food_repeat_2[2]/food_group_2/Orange",
            "food_repeat_2[2]/food_group_2/Banana",
            "food_repeat_2[2]/food_group_2/Pizza",
            "food_repeat_2[2]/food_group_2/Lasgna",
            "food_repeat_2[2]/food_group_2/Cake",
            "food_repeat_2[2]/food_group_2/Chocolate",
            "food_repeat_2[2]/food_group_2/Salad",
            "food_repeat_2[2]/food_group_2/Sandwich",
            "gps",
            "_gps_latitude",
            "_gps_longitude",
            "_gps_altitude",
            "_gps_precision",
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

        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, self.xform.id_string, include_images=False
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        csv_df_builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)

        self.assertEqual(header, expected_header)

        csv_file.close()

    def test_split_select_multiples_with_randomize(self):
        """
        Test select multiples choices are split with the randomize option true.
        """
        md_xform = """
        | survey |
        |        | type                     | name         | label        | parameters     |
        |        | text                     | name         | Name         |                |
        |        | integer                  | age          | Age          |                |
        |        | begin repeat             | browser_use  | Browser Use  |                |
        |        | integer                  | year         | Year         |                |
        |        | select_multiple browsers | browsers     | Browsers     | randomize=true |
        |        | end repeat               |              |              |                |

        | choices |
        |         | list name | name    | label             |
        |         | browsers  | firefox | Firefox           |
        |         | browsers  | chrome  | Chrome            |
        |         | browsers  | ie      | Internet Explorer |
        |         | browsers  | safari  | Safari            |
        """  # noqa: E501
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [
            {
                "name": "Tom",
                "age": 23,
                "browser_use": [
                    {
                        "browser_use/year": "2010",
                        "browser_use/browsers": "firefox safari",
                    },
                    {
                        "browser_use/year": "2011",
                        "browser_use/browsers": "firefox chrome",
                    },
                ],
            }
        ]  # yapf: disable
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=True,
            include_images=False,
        )
        record = cursor[0]
        select_multiples = CSVDataFrameBuilder._collect_select_multiples(xform)
        result = CSVDataFrameBuilder._split_select_multiples(record, select_multiples)
        # build a new dictionary only composed of the keys we want to use in
        # the comparison
        result = dict(
            [(key, result[key]) for key in list(result) if key in list(cursor[0])]
        )
        self.assertEqual(cursor[0], result)
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username, xform.id_string, binary_select_multiples=True
        )
        # pylint: disable=protected-access
        result = csv_df_builder._split_select_multiples(record, select_multiples)
        # build a new dictionary only composed of the keys we want to use in
        # the comparison
        result = dict(
            [(key, result[key]) for key in list(result) if key in list(cursor[0])]
        )
        self.assertEqual(cursor[0], result)

    def test_select_multiples_grouped_repeating_w_split(self):
        """Select multiple choices within group within repeat with split"""
        md_xform = """
        | survey  |                          |              |                   |
        |         | type                     | name         | label             |
        |         | text                     | name         | Name              |
        |         | integer                  | age          | Age               |
        |         | begin group              | grp1         | Group 1           |
        |         | begin group              | grp2         | Group 2           |
        |         | begin repeat             | browser_use  | Browser Use       |
        |         | begin group              | grp3         | Group 3           |
        |         | begin group              | grp4         | Group 4           |
        |         | begin group              | grp5         | Group 5           |
        |         | integer                  | year         | Year              |
        |         | select_multiple browsers | browsers     | Browsers          |
        |         | end group                |              |                   |
        |         | end group                |              |                   |
        |         | end group                |              |                   |
        |         | end repeat               |              |                   |
        |         | end group                |              |                   |
        |         | end group                |              |                   |
        | choices |                          |              |                   |
        |         | list_name                | name         | label             |
        |         | browsers                 | firefox      | Firefox           |
        |         | browsers                 | chrome       | Chrome            |
        |         | browsers                 | ie           | Internet Explorer |
        |         | browsers                 | safari       | Safari            |"""

        xform = self._publish_markdown(md_xform, self.user, id_string="nested_split")
        cursor = [
            {
                "name": "Bob",
                "age": 24,
                "grp1/grp2/browser_use": [
                    {
                        "grp1/grp2/browser_use/grp3/grp4/grp5/year": "2010",
                        "grp1/grp2/browser_use/grp3/grp4/grp5/browsers": "firefox safari",
                    },
                    {
                        "grp1/grp2/browser_use/grp3/grp4/grp5/year": "2011",
                        "grp1/grp2/browser_use/grp3/grp4/grp5/browsers": "firefox chrome",
                    },
                ],
            },
        ]
        builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=True,
            include_images=False,
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        expected_header = [
            "name",
            "age",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/year",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/browsers/firefox",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/browsers/chrome",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/browsers/ie",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/browsers/safari",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/year",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/browsers/firefox",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/browsers/chrome",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/browsers/ie",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/browsers/safari",
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
        self.assertEqual(header, expected_header)
        row = next(csv_reader)
        expected_row = [
            "Bob",
            "24",
            "2010",
            "True",
            "False",
            "False",
            "True",
            "2011",
            "True",
            "True",
            "False",
            "False",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
        ]
        self.assertEqual(row, expected_row)

        csv_file.close()

    def test_select_multiples_grouped_repeating_wo_split(self):
        """Select multiple choices within group within repeat without split"""
        md_xform = """
        | survey  |                          |              |                   |
        |         | type                     | name         | label             |
        |         | text                     | name         | Name              |
        |         | integer                  | age          | Age               |
        |         | begin group              | grp1         | Group 1           |
        |         | begin group              | grp2         | Group 2           |
        |         | begin repeat             | browser_use  | Browser Use       |
        |         | begin group              | grp3         | Group 3           |
        |         | begin group              | grp4         | Group 4           |
        |         | begin group              | grp5         | Group 5           |
        |         | integer                  | year         | Year              |
        |         | select_multiple browsers | browsers     | Browsers          |
        |         | end group                |              |                   |
        |         | end group                |              |                   |
        |         | end group                |              |                   |
        |         | end repeat               |              |                   |
        |         | end group                |              |                   |
        |         | end group                |              |                   |
        | choices |                          |              |                   |
        |         | list_name                | name         | label             |
        |         | browsers                 | firefox      | Firefox           |
        |         | browsers                 | chrome       | Chrome            |
        |         | browsers                 | ie           | Internet Explorer |
        |         | browsers                 | safari       | Safari            |"""

        xform = self._publish_markdown(md_xform, self.user, id_string="nested_split")
        cursor = [
            {
                "name": "Bob",
                "age": 24,
                "grp1/grp2/browser_use": [
                    {
                        "grp1/grp2/browser_use/grp3/grp4/grp5/year": "2010",
                        "grp1/grp2/browser_use/grp3/grp4/grp5/browsers": "firefox safari",
                    },
                    {
                        "grp1/grp2/browser_use/grp3/grp4/grp5/year": "2011",
                        "grp1/grp2/browser_use/grp3/grp4/grp5/browsers": "firefox chrome",
                    },
                ],
            },
        ]
        builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        expected_header = [
            "name",
            "age",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/year",
            "grp1/grp2/browser_use[1]/grp3/grp4/grp5/browsers",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/year",
            "grp1/grp2/browser_use[2]/grp3/grp4/grp5/browsers",
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
        self.assertEqual(header, expected_header)
        row = next(csv_reader)
        expected_row = [
            "Bob",
            "24",
            "2010",
            "firefox safari",
            "2011",
            "firefox chrome",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
            "n/a",
        ]
        self.assertEqual(row, expected_row)

        csv_file.close()

    def test_entity_list_dataset(self):
        """Export for an EntityList dataset is correct"""
        # Publish registration form
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})|                          |                                            |"""
        xform = self._publish_markdown(md, self.user)
        entity_list = EntityList.objects.first()
        cursor = [
            {
                "name": 1,
                "label": "300cm purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
            }
        ]
        builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            include_images=False,
            entity_list=entity_list,
        )
        temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
        builder.export_to(temp_file.name, cursor)
        csv_file = open(temp_file.name, "r")
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader)
        expected_header = [
            "name",
            "label",
            "geometry",
            "species",
            "circumference_cm",
        ]
        self.assertCountEqual(header, expected_header)
        expected_row = [
            "1",
            "300cm purpleheart",
            "-1.286905 36.772845 0 0",
            "purpleheart",
            "300",
        ]
        row = next(csv_reader)
        self.assertCountEqual(row, expected_row)

    def test_extra_columns_dataview(self):
        """Extra columns are included in export for dataview

        Extra columns included only if in the dataview
        """
        md_xform = """
        | survey  |
        |         | type                   | name  | label  |
        |         | text                   | name  | Name   |
        |         | integer                | age   | Age    |
        |         | select_multiple fruits | fruit | Fruit  |
        |         |                        |       |        |
        | choices | list name              | name  | label  |
        |         | fruits                 | 1     | Mango  |
        |         | fruits                 | 2     | Orange |
        |         | fruits                 | 3     | Apple  |
        """
        xform = self._publish_markdown(md_xform, self.user, id_string="b")
        cursor = [{"name": "Maria", "age": 25, "fruit": "1 2"}]
        csv_df_builder = CSVDataFrameBuilder(
            self.user.username,
            xform.id_string,
            split_select_multiples=False,
            include_images=False,
            show_choice_labels=True,
        )
        extra_cols = [
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

        for extra_col in extra_cols:
            dataview = DataView.objects.create(
                xform=xform,
                name="test",
                columns=["age", extra_col],
                project=self.project,
            )
            temp_file = NamedTemporaryFile(suffix=".csv", delete=False)
            csv_df_builder.export_to(temp_file.name, cursor, dataview=dataview)
            csv_file = open(temp_file.name, "r")
            csv_reader = csv.reader(csv_file)
            header = next(csv_reader)
            self.assertEqual(header, ["age", extra_col])
