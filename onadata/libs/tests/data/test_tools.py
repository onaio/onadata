# -*- coding: utf-8 -*-
"""
Test onadata.libs.data.query module
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.data.query import (
    get_date_fields,
    get_field_records,
    get_form_submissions_grouped_by_field,
)


class TestTools(TestBase):
    """
    Test onadata.libs.data.query module
    """

    def setUp(self):
        super().setUp()
        self._create_user_and_login()
        self._publish_transportation_form()

    @patch("django.utils.timezone.now")
    def test_get_form_submissions_grouped_by_field(self, mock_time):
        mock_time.return_value = datetime.utcnow().replace(tzinfo=timezone.utc)
        self._make_submissions()

        count_key = "count"
        fields = ["_submission_time", "_xform_id_string"]

        count = len(self.xform.instances.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(self.xform, field)[0]

            self.assertEqual([field, count_key], sorted(list(result)))
            self.assertEqual(result[count_key], count)

    def test_get_form_submissions_grouped_by_field_datetime(
        self,
    ):  # pylint: disable=invalid-name
        """Test get_form_submissions_grouped_by_field datetime"""
        now = datetime(2014, 1, 1, tzinfo=timezone.utc)
        times = [
            now,
            now + timedelta(seconds=1),
            now + timedelta(seconds=2),
            now + timedelta(seconds=3),
        ]
        self._make_submissions()

        for i in self.xform.instances.all().order_by("-pk"):
            i.date_created = times.pop()
            i.save()

        count_key = "count"
        fields = ["_submission_time"]

        count = len(self.xform.instances.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(self.xform, field)[0]

            self.assertEqual([field, count_key], sorted(list(result)))
            self.assertEqual(result[field], str(now.date()))
            self.assertEqual(result[count_key], count)

    @patch("django.utils.timezone.now")
    def test_get_form_submissions_two_xforms(self, mock_time):
        mock_time.return_value = datetime.utcnow().replace(tzinfo=timezone.utc)
        self._make_submissions()
        self._publish_xls_file(os.path.join("fixtures", "gps", "gps.xlsx"))

        first_xform = self.xform
        xform = self.user.xforms.all().order_by("-pk")[0]

        self._make_submission(
            os.path.join(
                "onadata",
                "apps",
                "main",
                "tests",
                "fixtures",
                "gps",
                "instances",
                "gps_1980-01-23_20-52-08.xml",
            )
        )

        count_key = "count"
        fields = ["_submission_time", "_xform_id_string"]

        count = len(xform.instances.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(xform, field)[0]

            self.assertEqual([field, count_key], sorted(list(result)))
            self.assertEqual(result[count_key], count)

        count = len(first_xform.instances.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(first_xform, field)[0]

            self.assertEqual([field, count_key], sorted(list(result)))
            self.assertEqual(result[count_key], count)

    @patch("django.utils.timezone.now")
    def test_get_form_submissions_xform_no_submissions(self, mock_time):
        mock_time.return_value = datetime.utcnow().replace(tzinfo=timezone.utc)
        self._make_submissions()
        self._publish_xls_file(os.path.join("fixtures", "gps", "gps.xlsx"))

        xform = self.user.xforms.all().order_by("-pk")[0]

        fields = ["_submission_time", "_xform_id_string"]

        count = len(xform.instances.all())
        self.assertEqual(count, 0)
        for field in fields:
            result = get_form_submissions_grouped_by_field(xform, field)
            self.assertEqual(result, [])

    @patch("django.utils.timezone.now")
    def test_get_form_submissions_grouped_by_field_sets_name(self, mock_time):
        mock_time.return_value = datetime.utcnow().replace(tzinfo=timezone.utc)
        self._make_submissions()

        count_key = "count"
        fields = ["_submission_time", "_xform_id_string"]
        name = "_my_name"

        xform = self.user.xforms.all()[0]
        count = len(xform.instances.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(xform, field, name)[0]

            self.assertEqual([name, count_key], sorted(list(result)))
            self.assertEqual(result[count_key], count)

    def test_get_form_submissions_when_response_not_provided(self):
        """
        Test that the None value is stripped when of the submissions
        doesnt have a response for the specified field
        """
        self._make_submissions()

        count = Instance.objects.count()

        # make submission that doesnt have a response for
        # `available_transportation_types_to_referral_facility`
        path = os.path.join(
            self.this_directory,
            "fixtures",
            "transportation",
            "instances",
            "transport_no_response",
            "transport_no_response.xml",
        )
        self._make_submission(path, self.user.username)
        self.assertEqual(Instance.objects.count(), count + 1)

        field = "transport/available_transportation_types_to_referral_facility"
        xform = self.user.xforms.all()[0]

        results = get_form_submissions_grouped_by_field(
            xform, field, "available_transportation_types_to_referral_facility"
        )

        # we should have a similar number of aggregates as submissions as each
        # submission has a unique value for the field
        self.assertEqual(len(results), count + 1)

        # the count where the value is None should have a count of 1
        result = [
            r
            for r in results
            if r["available_transportation_types_to_referral_facility"] is None
        ][0]
        self.assertEqual(result["count"], 1)

    def test_get_date_fields_includes_start_end(self):
        path = os.path.join(
            os.path.dirname(__file__), "fixtures", "tutorial", "tutorial.xlsx"
        )
        self._publish_xls_file_and_set_xform(path)
        fields = get_date_fields(self.xform)
        expected_fields = sorted(
            ["_submission_time", "date", "start_time", "end_time", "today", "exactly"]
        )
        self.assertEqual(sorted(fields), expected_fields)

    def test_get_field_records_when_some_responses_are_empty(self):
        submissions = ["1", "2", "3", "no_age"]
        path = os.path.join(
            os.path.dirname(__file__), "fixtures", "tutorial", "tutorial.xlsx"
        )
        self._publish_xls_file_and_set_xform(path)

        for i in submissions:
            self._make_submission(
                os.path.join(
                    "onadata",
                    "apps",
                    "api",
                    "tests",
                    "fixtures",
                    "forms",
                    "tutorial",
                    "instances",
                    f"{i}.xml",
                )
            )

        field = "age"
        records = get_field_records(field, self.xform)
        self.assertEqual(sorted(records), sorted([23, 23, 35]))

    def test_group_by_field_name_with_double_quote(self):
        """A group name containing a double quote is grouped safely as an alias."""
        self._make_submissions()
        field = "_submission_time"
        name = 'a"b'

        result = get_form_submissions_grouped_by_field(self.xform, field, name)[0]

        self.assertEqual(sorted([name, "count"]), sorted(list(result)))
        self.assertEqual(result["count"], len(self.xform.instances.all()))

    def test_group_by_field_with_quoted_data_view_filter(self):
        """A single quote in a data view filter value is compared as a literal."""
        self._make_submissions()
        data_view = DataView.objects.create(
            name="dv",
            project=self.xform.project,
            xform=self.xform,
            columns=["name"],
            query=[
                {
                    "column": "name",
                    "filter": "=",
                    "value": "x' OR '1'='1",
                    "condition": "and",
                }
            ],
        )

        result = get_form_submissions_grouped_by_field(
            self.xform, "_submission_time", data_view=data_view
        )

        # The value is treated as a literal that matches no submission; if it
        # were injected the trailing OR '1'='1' would match every row.
        self.assertEqual(result, [])

    def _executed_group_by_query(self, field, data_view=None):
        """Run the public group-by path with a mocked cursor and return the
        ``(sql, params)`` handed to ``cursor.execute``.

        Asserting here checks the real psycopg2 hand-off — the SQL text the
        driver receives and the values bound alongside it — without reaching
        into the private query builders.
        """
        with patch("onadata.libs.data.query.connection") as mock_connection:
            cursor = mock_connection.cursor.return_value
            cursor.description = []
            cursor.fetchall.return_value = []
            get_form_submissions_grouped_by_field(
                self.xform, field, data_view=data_view
            )
        sql, params = cursor.execute.call_args.args
        return sql, params

    def test_group_by_field_binds_hostile_filter_as_params(self):
        """Hostile filter column/value are bound as params, never in SQL text.

        Covers a literal ``%s``, a single quote and a backslash across two AND
        filters, and asserts the placeholder count equals the parameter count.
        """
        data_view = DataView(
            xform=self.xform,
            query=[
                {
                    "column": ") OR 1=1 --",
                    "filter": "=",
                    "value": "A%s",
                    "condition": "and",
                },
                {
                    "column": "name",
                    "filter": "=",
                    "value": "b\\c' OR '1'='1",
                    "condition": "and",
                },
            ],
        )

        sql, params = self._executed_group_by_query("_submission_time", data_view)

        # No request-derived filter token is rendered into the SQL text.
        self.assertNotIn(") OR 1=1 --", sql)
        self.assertNotIn("A%s", sql)
        self.assertNotIn("b\\c", sql)
        self.assertNotIn("OR '1'='1", sql)
        # Every placeholder is backed by exactly one bound parameter, in order.
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params, [") OR 1=1 --", "A%s", "name", "b\\c' OR '1'='1"])

    def test_group_by_field_percent_s_shift_preserves_param_order(self):
        """A literal ``%s`` in an earlier value cannot shift a later column out.

        This is the prior-escaping-bypass primitive: a one-at-a-time replace
        loop re-scanned inserted text, so a ``%s`` in an earlier value shifted
        the following column outside its quotes. With bound parameters the
        column and value are never rendered into SQL, so ordering is preserved.
        """
        data_view = DataView(
            xform=self.xform,
            query=[
                {"column": "age", "filter": "=", "value": "A%s", "condition": "and"},
                {
                    "column": ") OR 1=1 --",
                    "filter": "=",
                    "value": "B",
                    "condition": "and",
                },
            ],
        )

        sql, params = self._executed_group_by_query("_submission_time", data_view)

        self.assertNotIn(") OR 1=1 --", sql)
        self.assertNotIn("OR 1=1", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params, ["age", "A%s", ") OR 1=1 --", "B"])

    def test_group_by_field_or_condition_param_order(self):
        """OR filters keep their column/value parameters in emitted order."""
        data_view = DataView(
            xform=self.xform,
            query=[
                {"column": "age", "filter": "=", "value": "1", "condition": "or"},
                {"column": "name", "filter": "=", "value": "2", "condition": "or"},
            ],
        )

        sql, params = self._executed_group_by_query("_submission_time", data_view)

        self.assertIn(" OR ", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params, ["age", "1", "name", "2"])

    def test_group_by_field_preserves_data_view_filter_types(self):
        """DataView filters retain the form's numeric and date SQL casts."""
        data_view = DataView(
            xform=self.xform,
            query=[
                {"column": "age", "filter": ">", "value": "20"},
                {"column": "visit_date", "filter": ">=", "value": "2020-01-01"},
                {"column": "score", "filter": "<", "value": "20.5"},
            ],
        )

        with patch.object(DataView, "get_known_integers", return_value=["age"]):
            with patch.object(DataView, "get_known_dates", return_value=["visit_date"]):
                with patch.object(
                    DataView, "get_known_decimals", return_value=["score"]
                ):
                    sql, params = self._executed_group_by_query(
                        "_submission_time", data_view
                    )

        self.assertIn("CAST(json->>%s AS INT) > %s", sql)
        self.assertIn("CAST(json->>%s AS TIMESTAMP) >= %s", sql)
        self.assertIn("CAST(JSON->>%s AS DECIMAL) < %s", sql)
        self.assertEqual(
            params,
            ["age", "20", "visit_date", "2020-01-01", "score", "20.5"],
        )

    def test_group_by_field_without_data_view_binds_no_params(self):
        """Without a DataView the driver receives the query with no bound params."""
        sql, params = self._executed_group_by_query("_submission_time")

        # ``params or None`` sends ``None`` so the driver skips ``%`` interpolation.
        self.assertIsNone(params)
        self.assertEqual(sql.count("%s"), 0)

    def test_group_by_field_percent_s_shift_returns_no_rows(self):
        """End-to-end: the %s-shift payload binds as data and matches nothing."""
        self._make_submissions()
        data_view = DataView.objects.create(
            name="dv-shift",
            project=self.xform.project,
            xform=self.xform,
            columns=["name"],
            query=[
                {"column": "name", "filter": "=", "value": "A%s", "condition": "and"},
                {
                    "column": ") OR 1=1 --",
                    "filter": "=",
                    "value": "B",
                    "condition": "and",
                },
            ],
        )

        result = get_form_submissions_grouped_by_field(
            self.xform, "_submission_time", data_view=data_view
        )

        # If the column injected, ") OR 1=1 --" would match every row; bound as
        # a JSON key it matches nothing.
        self.assertEqual(result, [])
