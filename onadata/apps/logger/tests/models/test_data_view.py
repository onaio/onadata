import os
from builtins import str

from django.conf import settings
from django.db import connection

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models.data_view import DataView, append_where_list
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.tests.test_base import TestBase


class TestDataView(TestBase):
    def test_append_where_list(self):
        json_str = "json->>%s"
        self.assertEqual(append_where_list("<>", [], json_str), ["json->>%s <> %s"])
        self.assertEqual(append_where_list("!=", [], json_str), ["json->>%s <> %s"])
        self.assertEqual(append_where_list("=", [], json_str), ["json->>%s = %s"])
        self.assertEqual(append_where_list(">", [], json_str), ["json->>%s > %s"])
        self.assertEqual(append_where_list("<", [], json_str), ["json->>%s < %s"])
        self.assertEqual(append_where_list(">=", [], json_str), ["json->>%s >= %s"])
        self.assertEqual(append_where_list("<=", [], json_str), ["json->>%s <= %s"])

    def test_restore_deleted(self):
        """Soft deleted DataView can be restored"""
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)
        # Create dataview for form and soft delete it
        data_view = DataView.objects.create(
            name="test_view",
            project=self.project,
            xform=xform,
            columns=["name", "age"],
        )
        data_view.soft_delete()
        data_view.refresh_from_db()

        self.assertIsNotNone(data_view.deleted_at)
        self.assertIn("-deleted-at-", data_view.name)

        # Restore DataView
        data_view.restore()
        data_view.refresh_from_db()

        self.assertIsNone(data_view.deleted_at)
        self.assertNotIn("-deleted-at-", data_view.name)


class TestIntegratedDataView(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()

        self.start_index = None
        self.limit = None
        self.count = None
        self.last_submission_time = False
        self.all_data = False
        self.sort = None

        self._setup_dataview()

        self.cursor = connection.cursor()

    def _setup_dataview(self):
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)

        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)
            x += 1

        self._create_dataview()

    def test_generate_query_string_for_data_without_filter(self):
        expected_sql = (
            "SELECT json FROM "
            "logger_instance WHERE xform_id = %s  AND "
            "CAST(json->>%s AS INT) > %s AND "
            "CAST(json->>%s AS INT) < %s AND deleted_at IS NULL"
            " ORDER BY id"
        )

        (sql, columns, params) = DataView.generate_query_string(
            self.data_view,
            self.start_index,
            self.limit,
            self.last_submission_time,
            self.all_data,
            self.sort,
        )

        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(columns), 8)

        self.cursor.execute(sql, [str(i) for i in (params)])
        results = self.cursor.fetchall()

        self.assertEqual(len(results), 3)

    def test_generate_query_string_for_data_with_limit_filter(self):
        limit_filter = 1
        expected_sql = (
            "SELECT json FROM logger_instance"
            " WHERE xform_id = %s  AND CAST(json->>%s AS INT) > %s"
            " AND CAST(json->>%s AS INT) < %s AND deleted_at "
            "IS NULL ORDER BY id LIMIT %s"
        )

        (sql, columns, params) = DataView.generate_query_string(
            self.data_view,
            self.start_index,
            limit_filter,
            self.last_submission_time,
            self.all_data,
            self.sort,
        )

        self.assertEqual(sql, expected_sql)

        records = [
            record
            for record in DataView.query_iterator(sql, columns, params, self.count)
        ]

        self.assertEqual(len(records), limit_filter)

    def test_generate_query_string_for_data_with_start_index_filter(self):
        start_index = 2
        expected_sql = (
            "SELECT json FROM logger_instance WHERE"
            " xform_id = %s  AND CAST(json->>%s AS INT) > %s AND"
            " CAST(json->>%s AS INT) < %s AND deleted_at IS NULL "
            "ORDER BY id OFFSET %s"
        )

        (sql, columns, params) = DataView.generate_query_string(
            self.data_view,
            start_index,
            self.limit,
            self.last_submission_time,
            self.all_data,
            self.sort,
        )

        self.assertEqual(sql, expected_sql)

        records = [
            record
            for record in DataView.query_iterator(sql, columns, params, self.count)
        ]
        self.assertEqual(len(records), 1)
        self.assertIn("name", records[0])
        self.assertIn("age", records[0])
        self.assertIn("gender", records[0])
        self.assertNotIn("pizza_type", records[0])

    def test_generate_query_string_for_data_with_sort_column_asc(self):
        sort = '{"age":1}'
        expected_sql = (
            "SELECT json FROM logger_instance WHERE"
            " xform_id = %s  AND CAST(json->>%s AS INT) > %s AND"
            " CAST(json->>%s AS INT) < %s AND deleted_at IS NULL"
            " ORDER BY  logger_instance.json->>%s ASC"
        )

        (sql, columns, params) = DataView.generate_query_string(
            self.data_view,
            self.start_index,
            self.limit,
            self.last_submission_time,
            self.all_data,
            sort,
        )

        self.assertEqual(sql, expected_sql)

        records = [
            record
            for record in DataView.query_iterator(sql, columns, params, self.count)
        ]

        self.assertTrue(self.is_sorted_asc([r.get("age") for r in records]))

    def test_generate_query_string_for_data_with_sort_column_desc(self):
        sort = '{"age": -1}'
        expected_sql = (
            "SELECT json FROM logger_instance WHERE"
            " xform_id = %s  AND CAST(json->>%s AS INT) > %s AND"
            " CAST(json->>%s AS INT) < %s AND deleted_at IS NULL"
            " ORDER BY  logger_instance.json->>%s DESC"
        )

        (sql, columns, params) = DataView.generate_query_string(
            self.data_view,
            self.start_index,
            self.limit,
            self.last_submission_time,
            self.all_data,
            sort,
        )

        self.assertEqual(sql, expected_sql)

        records = [
            record
            for record in DataView.query_iterator(sql, columns, params, self.count)
        ]

        self.assertTrue(self.is_sorted_desc([r.get("age") for r in records]))
