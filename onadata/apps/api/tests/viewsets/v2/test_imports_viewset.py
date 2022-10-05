"""
Module containing tests for the ImportsViewSet
"""
import os

from typing import IO, Any
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from httmock import HTTMock

from onadata.celeryapp import app
from onadata.apps.api.viewsets.v2.imports_viewset import ImportsViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tests.mocked_data import enketo_mock


def fixtures_path(filepath: str) -> IO[Any]:
    """Returns the file object at the given filepath."""
    return open(
        os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", filepath
        ),
        "rb",
    )


class TestImportsViewSet(TestAbstractViewSet):
    def setUp(self):
        super(TestImportsViewSet, self).setUp()
        self.view = ImportsViewSet.as_view({"post": "create", "get": "retrieve"})

    @override_settings(DISABLE_ASYNCHRONOUS_IMPORTS=True)
    def test_create_expected_synchronous_response(self):
        """
        Tests that the `api/v2/imports/<xform-id>` route processes a request
        successfully when `DISABLE_ASYNCHRONOUS_IMPORTS` is set to `True`
        """
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            form = self.project.xform_set.first()
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post(
                f"/api/v2/imports/{form.pk}", data=post_data, **self.extra
            )
            response = self.view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("additions"), 9)
            self.assertEqual(response.data.get("updates"), 0)

    def test_create_expected_async_response(self):
        """
        Tests that the `api/v2/imports/<xform-id>` route processes a request
        successfully when `DISABLE_ASYNCHRONOUS_IMPORTS` is set to `False`
        """
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            form = self.project.xform_set.first()
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post(
                "/api/v2/imports/{form.pk}", data=post_data, **self.extra
            )
            response = self.view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.content_type, "application/json")
            expected_fields = ["task_id"]
            self.assertEqual(expected_fields, list(response.data.keys()))

    @patch("onadata.apps.api.viewsets.v2.imports_viewset.get_active_tasks")
    def test_create_ongoing_overwrite_task(self, mocked_get_active_tasks):
        """
        Test that the `api/v2/imports/<xform-id>` route refuses to process request
        when an overwrite import task is ongoing
        """
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            form = self.project.xform_set.first()
            path = "/api/v2/imports/{form.pk}"
            mocked_get_active_tasks.return_value = '[{"job_uuid": "11", "time_start": "1664372983.8631873", "file": "good.csv", "overwrite": true}]'

            # Test that request fails when csv_file & xls_file are not sent
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post(path, data=post_data, **self.extra)
            response = self.view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {
                "reason": "An ongoing overwrite request with the ID 11 is being processed"
            }
            self.assertEqual(expected_response, response.data)

    def test_create_request_validation(self):
        """
        Tests that the `api/v2/imports/<xform-id>` route validates requests.

        Expected Validations:
          - Checks that either `xls_file` or `csv_file` is sent
          - Checks that `xls_file` is an XLS File
          - Checks that `csv_file` is a CSV File
        """
        with HTTMock(enketo_mock):
            xls_path = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "tutorial.xlsx",
            )
            self._publish_xls_form_to_project(xlsform_path=xls_path)
            form = self.project.xform_set.first()
            path = "/api/v2/imports/{form.pk}"

            # Test that request fails when csv_file & xls_file are not sent
            request = self.factory.post(path, **self.extra)
            response = self.view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {"error": "csv_file and xls_file field empty"}
            self.assertEqual(expected_response, response.data)

            # Test that request fails when csv_file or xls_file
            # has the incorrect extension
            csv_import = fixtures_path("good.csv")
            post_data = {"xls_file": csv_import}
            request = self.factory.post(path, data=post_data, **self.extra)
            response = self.view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {"error": "xls_file not an excel file"}
            self.assertEqual(expected_response, response.data)

            post_data = {"csv_file": open(xls_path, "rb")}
            request = self.factory.post(path, data=post_data, **self.extra)
            response = self.view(request, pk=self.xform.id)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {"error": "csv_file not a csv file"}
            self.assertEqual(expected_response, response.data)
