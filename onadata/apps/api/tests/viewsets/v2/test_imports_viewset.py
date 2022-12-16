"""
Module containing tests for the ImportsViewSet
"""
import os

from typing import IO, Any
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import override_settings
from httmock import HTTMock

from onadata.apps.api.viewsets.v2.imports_viewset import ImportsViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tests.mocked_data import enketo_mock
from onadata.apps.main.models import UserProfile
from onadata.libs.permissions import DataEntryRole, EditorRole


def fixtures_path(filepath: str) -> IO[Any]:
    """Returns the file object at the given filepath."""
    return open(
        os.path.join(settings.PROJECT_ROOT, "libs", "tests", "utils",
                     "fixtures", filepath),
        "rb",
    )


class TestImportsViewSet(TestAbstractViewSet):
    """
    Test for ImportsViewSet
    """

    def setUp(self):
        super().setUp()
        self.view = ImportsViewSet.as_view({
            "post": "create",
            "get": "retrieve",
            "delete": "destroy"
        })

    def test_create_permissions(self):
        """
        Tests that only users with Editor role or role superseding it can
        create imports
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
            user = get_user_model().objects.create(username="joe",
                                                   email="joe@example.com",
                                                   first_name="Joe")
            _ = UserProfile.objects.create(user=user)
            extra = {"HTTP_AUTHORIZATION": f"Token {user.auth_token}"}
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}

            # Unauthenticated request fails
            request = self.factory.post(f"/api/v2/imports/{self.xform.pk}",
                                        data=post_data)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 401)

            # User without permissions can not import data
            request = self.factory.post(f"/api/v2/imports/{self.xform.pk}",
                                        data=post_data,
                                        **extra)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                "You do not have permission to perform this action.",
                str(response.data.get("detail")),
            )

            # User with dataentry role can not import data
            DataEntryRole.add(user, self.xform)

            request = self.factory.post(f"/api/v2/imports/{self.xform.pk}",
                                        data=post_data,
                                        **extra)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                "You do not have permission to perform this action.",
                str(response.data.get("detail")),
            )

            # User with editor role can import data
            DataEntryRole.remove_obj_permissions(user, self.xform)
            EditorRole.add(user, self.xform)

            request = self.factory.post(f"/api/v2/imports/{self.xform.pk}",
                                        data=post_data,
                                        **extra)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 202)

    @override_settings(DISABLE_ASYNCHRONOUS_IMPORTS=True)
    def test_synchronous_response(self):
        """
        Tests that the `api/v2/imports/<xself.xform.pk>` route processes a request
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
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post(f"/api/v2/imports/{self.xform.pk}",
                                        data=post_data,
                                        **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.data.get("additions"), 9)
            self.assertEqual(response.data.get("updates"), 0)

    def test_expected_async_response(self):
        """
        Tests that the `api/v2/imports/<xself.xform.pk>` route processes a request
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
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}

            # import ipdb; ipdb.set_trace()
            request = self.factory.post("/api/v2/imports/{self.xform.pk}",
                                        data=post_data,
                                        **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.content_type, "application/json")
            expected_fields = ["task_id"]
            self.assertEqual(expected_fields, list(response.data.keys()))

    @patch("onadata.apps.api.viewsets.v2.imports_viewset.get_active_tasks")
    def test_ongoing_overwrite_task(self, mocked_get_active_tasks):
        """
        Test that the `api/v2/imports/<xself.xform.pk>` route refuses to process request
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
            path = "/api/v2/imports/{self.xform.pk}"
            mocked_get_active_tasks.return_value = [{
                "job_uuid": "11",
                "time_start": "1664372983.8631873",
                "file": "good.csv",
                "overwrite": True
            }]

            # Test that request fails when csv_file & xls_file are not sent
            csv_import = fixtures_path("good.csv")
            post_data = {"csv_file": csv_import}
            request = self.factory.post(path, data=post_data, **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.content_type, "application/json")
            self.assertEqual(
                "An ongoing overwrite request with the ID 11 is being processed",
                str(response.data.get("detail")),
            )

    def test_create_request_validation(self):
        """
        Tests that the `api/v2/imports/<xself.xform.pk>` route validates requests.

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
            path = "/api/v2/imports/{self.xform.pk}"

            # Test that request fails when csv_file & xls_file are not sent
            request = self.factory.post(path, **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {"error": "csv_file and xls_file field empty"}
            self.assertEqual(expected_response, response.data)

            # Test that request fails when csv_file or xls_file
            # has the incorrect extension
            csv_import = fixtures_path("good.csv")
            post_data = {"xls_file": csv_import}
            request = self.factory.post(path, data=post_data, **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {"error": "xls_file not an excel file"}
            self.assertEqual(expected_response, response.data)

            with open(xls_path, "rb") as xls_file:
                post_data = {"csv_file": xls_file}
                request = self.factory.post(path, data=post_data, **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content_type, "application/json")
            expected_response = {"error": "csv_file not a csv file"}
            self.assertEqual(expected_response, response.data)

    def test_delete_permissions(self):
        """
        Tests that only users with Editor role or role superseding it can
        terminate imports
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
            path = "/api/v2/imports/{self.xform.pk}?task_uuid=11"
            user = get_user_model().objects.create(username="joe",
                                                   email="joe@example.com",
                                                   first_name="Joe")
            _ = UserProfile.objects.create(user=user)
            extra = {"HTTP_AUTHORIZATION": f"Token {user.auth_token}"}

            # Test that unauthenticated users can not terminate imports
            request = self.factory.delete(path)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 401)

            # Test that users without permissions to the form can not terminate imports
            request = self.factory.delete(path, **extra)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                "You do not have permission to perform this action.",
                str(response.data.get("detail")),
            )

            # Test that users with data entry permissions can not terminate imports
            DataEntryRole.add(user, self.xform)

            request = self.factory.delete(path, **extra)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                "You do not have permission to perform this action.",
                str(response.data.get("detail")),
            )

            # Test that users with editor role can terminate imports
            DataEntryRole.remove_obj_permissions(user, self.xform)
            EditorRole.add(user, self.xform)

            request = self.factory.delete(path, **extra)
            response = self.view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                {"error": "Queued task with ID 11 does not exist"},
                response.data)

    @patch("onadata.apps.api.viewsets.v2.imports_viewset.terminate_import_task"
           )
    def test_delete_expected_response(self, mocked_terminate_import_task):
        """
        Test that the `api/v2/imports/<xself.xform.pk>` DELETE route returns the
        expected successful response
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
            path = "/api/v2/imports/{self.xform.pk}?task_uuid=11"
            mocked_terminate_import_task.return_value = True

            request = self.factory.delete(path, **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 204)

    @patch("onadata.apps.api.viewsets.v2.imports_viewset.app")
    def test_delete_validation(self, mocked_celery_app):
        """
        Test that the `api/v2/imports/<xself.xform.pk>` DELETE route validates requests.

        Expected validation checks:
          - Checks that `task_uuid` is sent
          - Checks that the task_uuid actually exists and is tied to the form
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
            path = "/api/v2/imports/{self.xform.pk}"

            # Test that request fails without task_uuid query param
            request = self.factory.delete(path, **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                {"error": "The task_uuid query parameter is required"},
                response.data)

            # Test that request fails if task_uuid does not exist for form
            mocked_celery_app.control.inspect().query_task.return_value = {
                'hostname': {
                    "11": [
                        "active", {
                            "id": 11,
                            "args": [None, "0", "good.csv", True],
                        }
                    ]
                }
            }
            request = self.factory.delete(f"{path}?task_uuid=11", **self.extra)
            response = self.view(request, pk=self.xform.pk)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                {"error": "Queued task with ID 11 does not exist"},
                response.data)
