# -*- coding: utf-8 -*-
"""
test_export_viewset module
"""

import os
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils.dateparse import parse_datetime

from httmock import HTTMock
from moto import mock_aws
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from onadata.apps.api.tests.mocked_data import enketo_mock
from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import DataView, Project
from onadata.apps.main.models import MetaData, UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.libs.permissions import DataEntryMinorRole, EditorMinorRole, ReadOnlyRole
from onadata.libs.utils.export_tools import generate_export


class TestExportViewSet(TestBase):
    """
    Test ExportViewSet functionality.
    """

    def setUp(self):
        super(TestExportViewSet, self).setUp()
        self.factory = APIRequestFactory()
        self.formats = ["csv", "csvzip", "kml", "osm", "savzip", "xls", "xlsx", "zip"]
        self.view = ExportViewSet.as_view({"get": "retrieve"})

    def _create_export(self):
        # Create a temporary file in the 'exports' directory and
        # prevent it from being deleted automatically
        temp_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(temp_dir, exist_ok=True)
        dummy_export_file = NamedTemporaryFile(
            suffix=".xlsx", dir=temp_dir, delete=False
        )
        dummy_export_file.close()  # Explicitly close the file
        filename = os.path.basename(dummy_export_file.name)
        export = Export.objects.create(
            xform=self.xform, filename=filename, filedir="exports"
        )
        return export

    def test_export_response(self):
        """
        Test ExportViewSet retrieve has the correct headers in response.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        export = self._create_export()
        request = self.factory.get("/export")
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=export.pk)
        self.assertIn(export.filename, response.get("Content-Disposition"))

    def test_export_formats_present(self):
        """
        Test export formats are in ExportViewSet.renderer_classes.
        """
        renderer_formats = [rc.format for rc in self.view.cls.renderer_classes]

        for ext in self.formats:
            self.assertIn(ext, renderer_formats)

    def test_export_non_existent_file(self):
        """
        Test non existent primary key results in HTTP_404_NOT_FOUND.
        """
        self._create_user_and_login()
        non_existent_pk = 1525266252676
        for ext in self.formats:
            request = self.factory.get("/export")
            force_authenticate(request, user=self.user)
            response = self.view(request, pk=non_existent_pk, format=ext)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_list(self):
        """
        Test ExportViewSet list endpoint.
        """
        self._create_user_and_login()
        view = ExportViewSet.as_view({"get": "list"})
        request = self.factory.get("/export")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertFalse(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_public(self):
        """
        Test ExportViewSet list endpoint for public forms.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        self._create_export()
        view = ExportViewSet.as_view({"get": "list"})

        # Should be empty list when no xform filter is provided
        request = self.factory.get("/export")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.data, [])

        # Should not be empty list when xform filter is provided
        request = self.factory.get("/export", data={"xform": self.xform.pk})
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertNotEqual(response.data, [])
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_public_form(self):
        """
        Test ExportViewSet list endpoint for a single public form.
        """
        user_mosh = self._create_user("mosh", "mosh")
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        self._create_export()
        view = ExportViewSet.as_view({"get": "list"})
        request = self.factory.get("/export", {"xform": self.xform.pk})
        force_authenticate(request, user=user_mosh)
        response = view(request)
        self.assertTrue(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.xform.soft_delete(user=self.user)
        request = self.factory.get("/export", {"xform": self.xform.pk})
        force_authenticate(request, user=user_mosh)
        response = view(request)
        self.assertEqual(response.data, [])
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_public_project(self):
        """
        Test export of a public form for anonymous users.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        export = generate_export(
            Export.CSV_EXPORT, self.xform, None, {"extension": "csv"}
        )
        request = self.factory.get("/export")
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    # pylint: disable=C0103
    def test_export_public_authenticated(self):
        """
        Test export of a public form for authenticated users.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        export = generate_export(
            Export.CSV_EXPORT, self.xform, None, {"extension": "csv"}
        )
        request = self.factory.get("/export")
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_public_deleted_form_not_accessible(self):
        """
        Test export of a public deleted form returns HTTP_404_NOT_FOUND.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.shared = True
        self.xform.save()
        export = generate_export(
            Export.CSV_EXPORT, self.xform, None, {"extension": "csv"}
        )
        test_user = self._create_user("not_bob", "pass")
        self.xform.soft_delete(user=self.user)

        request = self.factory.get("/export")
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        request = self.factory.get("/export")
        force_authenticate(request, user=test_user)
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_export_public_not_owner_authenticated(self):
        """
        Test export of a public form for authenticated users.
        Not owners of the form.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.shared = True
        self.xform.save()
        test_user = self._create_user("not_bob", "pass")
        request = self.factory.get("/export")
        force_authenticate(request, user=test_user)
        # csv export
        export = generate_export(
            Export.CSV_EXPORT, self.xform, None, {"extension": "csv"}
        )
        export.options = {"query": {"_submitted_by": "not_bob"}}
        export.save()
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        # sav export
        export = generate_export(
            Export.SAV_ZIP_EXPORT, self.xform, None, {"extension": "zip"}
        )
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_non_public_export(self):
        """
        Test export of private data results in HTTP_404_NOT_FOUND response
        for users without access to it.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = False
        self.xform.save()
        export = generate_export(
            Export.CSV_EXPORT, self.xform, None, {"extension": "csv"}
        )
        request = self.factory.get("/export")
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        self.xform.shared = True
        self.xform.save()
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        no_role_request = self.factory.get("/export")
        force_authenticate(no_role_request, user=self._create_user("mosh", "mosh"))
        response = self.view(no_role_request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        owner_request = self.factory.get("/export")
        force_authenticate(owner_request, user=self.user)
        response = self.view(owner_request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # A dataview only reaches its own exports, whichever project it is in.
        dataview = DataView.objects.create(
            name="public dataview",
            xform=self.xform,
            project=Project.objects.create(
                name="public project",
                organization=self.user,
                created_by=self.user,
                shared=True,
            ),
            columns=["name"],
            query=[{"column": "name", "filter": "=", "value": "x"}],
        )
        dataview_export = generate_export(
            Export.CSV_EXPORT,
            self.xform,
            None,
            {"extension": "csv", "dataview_pk": dataview.pk},
        )
        self.assertEqual(dataview_export.options["dataview_pk"], dataview.pk)
        dataview_request = self.factory.get("/export", {"dataview": dataview.pk})

        def assert_only_dataview_export_is_reachable():
            response = self.view(dataview_request, pk=export.pk)
            self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
            response = self.view(dataview_request, pk=dataview_export.pk)
            self.assertEqual(status.HTTP_200_OK, response.status_code)

        assert_only_dataview_export_is_reachable()

        dataview.project.shared = False
        dataview.project.save()
        response = self.view(dataview_request, pk=dataview_export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        reader = self._create_user("reader", "reader")
        ReadOnlyRole.add(reader, dataview.project)
        force_authenticate(dataview_request, user=reader)
        assert_only_dataview_export_is_reachable()

        delete_request = self.factory.delete(f"/export?dataview={dataview.pk}")
        force_authenticate(delete_request, user=reader)
        delete_view = ExportViewSet.as_view({"delete": "destroy"})
        response = delete_view(delete_request, pk=dataview_export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertTrue(Export.objects.filter(pk=dataview_export.pk).exists())

    def test_export_list_checks_read_access_once_per_form(self):
        """Listing more dataview exports of a form runs no more queries."""
        self._create_user_and_login()
        self._publish_transportation_form()
        self.assertFalse(self.xform.shared_data)

        def create_dataview_export(dataview_pk):
            return Export.objects.create(
                xform=self.xform,
                export_type=Export.CSV_EXPORT,
                filename=f"dataview_{dataview_pk}.csv",
                internal_status=Export.SUCCESSFUL,
                options={"dataview_pk": dataview_pk},
            )

        def list_exports():
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=self.user)
            view = ExportViewSet.as_view({"get": "list"})
            with CaptureQueriesContext(connection) as queries:
                response = view(request)
                response.render()
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            return response.data, len(queries)

        create_dataview_export(1)
        # The first request fills the content type and user permission caches.
        list_exports()
        exports, single_export_queries = list_exports()
        self.assertEqual(1, len(exports))

        create_dataview_export(2)
        create_dataview_export(3)
        exports, three_export_queries = list_exports()
        self.assertEqual(3, len(exports))

        self.assertEqual(single_export_queries, three_export_queries)

    def test_export_list_on_user(self):
        """
        Test ExportViewSet list endpoint with xform filter.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        exports = [self._create_export()]
        view = ExportViewSet.as_view({"get": "list"})
        request = self.factory.get("/export", data={"xform": self.xform.id})
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(len(exports), len(response.data))
        self.assertEqual(exports[0].id, response.data[0].get("id"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_on_with_different_users(self):
        """
        Test ExportViewSet list endpoint with a different user.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self._create_export()
        view = ExportViewSet.as_view({"get": "list"})
        request = self.factory.get("/export", data={"xform": self.xform.id})
        self._create_user_and_login(username="mary", password="password1")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertFalse(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_delete(self):
        """
        Test deleting an export on ExportViewSet.
        """
        markdown_xlsform = """
        | survey |
        |        | type              | name  | label |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(markdown_xlsform, self.user)
        bob = self.user
        export = Export.objects.create(xform=xform)
        export.save()
        view = ExportViewSet.as_view({"delete": "destroy"})

        # mary has no access hence cannot delete
        self._create_user_and_login(username="mary", password="password1")
        request = self.factory.delete("/export")
        force_authenticate(request, user=self.user)
        response = view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        xform.shared_data = True
        xform.save()
        list_view = ExportViewSet.as_view({"get": "list"})
        response = list_view(self.factory.get("/export", {"xform": xform.pk}))
        self.assertEqual([export.pk], [item["id"] for item in response.data])
        response = view(self.factory.delete("/export"), pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertTrue(Export.objects.filter(pk=export.pk).exists())

        # bob has access hence can delete
        request = self.factory.delete("/export")
        force_authenticate(request, user=bob)
        response = view(request, pk=export.pk)
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

    def test_export_delete_null_body(self):
        """Null request body is handled"""
        markdown_xlsform = """
        | survey |
        |        | type              | name  | label |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(markdown_xlsform, self.user)
        bob = self.user
        export = Export.objects.create(xform=xform)
        export.save()
        view = ExportViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(
            "/export", data=None, content_type="application/json"
        )
        force_authenticate(request, user=bob)
        response = view(request, pk=export.pk)
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

    def test_export_list_with_meta_perms(self):
        """
        Test export list for forms with meta permissions.
        """
        with HTTMock(enketo_mock):
            self._publish_transportation_form()

            for survey in self.surveys:
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "apps",
                        "main",
                        "tests",
                        "fixtures",
                        "transportation",
                        "instances",
                        survey,
                        survey + ".xml",
                    ),
                    forced_submission_time=parse_datetime("2013-02-18 15:54:01Z"),
                )

            alice = self._create_user("alice", "alice", True)

            MetaData.xform_meta_permission(
                self.xform, data_value="editor|dataentry-minor|readonly-no-download"
            )

            DataEntryMinorRole.add(alice, self.xform)

            for i in self.xform.instances.all()[:2]:
                i.user = alice
                i.save()

            view = XFormViewSet.as_view({"get": "retrieve"})

            alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % alice.auth_token.key}

            # Alice creates an export with her own submissions
            request = self.factory.get("/", **alices_extra)
            response = view(request, pk=self.xform.pk, format="csv")
            self.assertEqual(response.status_code, 200)

            exports = Export.objects.filter(xform=self.xform)
            view = ExportViewSet.as_view({"get": "list"})
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=alice)
            response = view(request)
            self.assertEqual(len(exports), len(response.data))

            # Mary should not have access to the export with Alice's
            # submissions.
            self._create_user_and_login(username="mary", password="password1")
            self.assertEqual(self.user.username, "mary")

            # Mary should only view their own submissions.
            DataEntryMinorRole.add(self.user, self.xform)
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=self.user)
            response = view(request)
            self.assertFalse(bool(response.data), response.data)
            self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_async_with_meta_perms(self):
        """
        Test export list for forms with meta permissions on export_async.
        """
        with HTTMock(enketo_mock):
            self._publish_transportation_form()

            for survey in self.surveys:
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "apps",
                        "main",
                        "tests",
                        "fixtures",
                        "transportation",
                        "instances",
                        survey,
                        survey + ".xml",
                    ),
                    forced_submission_time=parse_datetime("2013-02-18 15:54:01Z"),
                )

            alice = self._create_user("alice", "alice", True)

            MetaData.xform_meta_permission(
                self.xform, data_value="editor|dataentry-minor|readonly-no-download"
            )

            DataEntryMinorRole.add(alice, self.xform)

            for i in self.xform.instances.all()[:2]:
                i.user = alice
                i.save()

            view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )

            alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % alice.auth_token.key}

            # Alice creates an export with her own submissions
            request = self.factory.get("/", data={"format": "csv"}, **alices_extra)
            response = view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 202)

            exports = Export.objects.filter(xform=self.xform)
            view = ExportViewSet.as_view({"get": "list"})
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=alice)
            response = view(request)
            self.assertEqual(len(exports), len(response.data))

            # Mary should not have access to the export with Alice's
            # submissions.
            self._create_user_and_login(username="mary", password="password1")
            self.assertEqual(self.user.username, "mary")

            # Mary should only view their own submissions.
            DataEntryMinorRole.add(self.user, self.xform)
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=self.user)
            response = view(request)
            self.assertFalse(bool(response.data), response.data)
            self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_readonly_with_meta_perms(self):
        """
        Test export list for forms with meta permissions on export_async.
        """
        with HTTMock(enketo_mock):
            self._publish_transportation_form()

            for survey in self.surveys:
                self._make_submission(
                    os.path.join(
                        settings.PROJECT_ROOT,
                        "apps",
                        "main",
                        "tests",
                        "fixtures",
                        "transportation",
                        "instances",
                        survey,
                        survey + ".xml",
                    ),
                    forced_submission_time=parse_datetime("2013-02-18 15:54:01Z"),
                )

            alice = self._create_user("alice", "alice", True)

            MetaData.xform_meta_permission(
                self.xform, data_value="editor|dataentry-minor|readonly-no-download"
            )

            ReadOnlyRole.add(alice, self.xform)

            export_view = XFormViewSet.as_view(
                {
                    "get": "export_async",
                }
            )

            alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % alice.auth_token.key}

            # Alice creates an export with her own submissions
            request = self.factory.get("/", data={"format": "csv"}, **alices_extra)
            response = export_view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 202)

            exports = Export.objects.filter(xform=self.xform)
            view = ExportViewSet.as_view({"get": "list"})
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=alice)
            response = view(request)
            self.assertEqual(len(exports), len(response.data))
            self.assertEqual(len(exports), 1)

            # Mary should not have access to the export with Alice's
            # submissions.
            self._create_user_and_login(username="mary", password="password1")
            self.assertEqual(self.user.username, "mary")

            # Mary should only view their own submissions.
            DataEntryMinorRole.add(self.user, self.xform)
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=self.user)
            response = view(request)
            self.assertFalse(bool(response.data), response.data)
            self.assertEqual(status.HTTP_200_OK, response.status_code)

            # assign some submissions to Mary
            for i in self.xform.instances.all()[:2]:
                i.user = self.user
                i.save()

            # Mary creates an export with her own submissions
            request = self.factory.get("/", data={"format": "csv"})
            force_authenticate(request, user=self.user)
            response = export_view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 202)

            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=self.user)
            response = view(request)
            self.assertTrue(bool(response.data), response.data)
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(Export.objects.filter(xform=self.xform).count(), 2)

            # Alice does not have access to the submitter only export
            request = self.factory.get("/export", data={"xform": self.xform.id})
            force_authenticate(request, user=alice)
            response = view(request)
            self.assertEqual(len(exports), len(response.data))
            self.assertEqual(len(exports), 1)

    def test_export_retrieval_authentication(self):
        """
        Test that users are able to authenticate with API token
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        export = self._create_export()
        extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token.key}"}

        request = self.factory.get("/export", **extra)
        response = self.view(request, pk=export.pk)
        self.assertEqual(response.status_code, 200)

    def test_export_failure_reason_returned(self):
        """
        Test that the reason an export failed is returned on the API
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        Export.objects.create(
            xform=self.xform,
            internal_status=Export.FAILED,
            error_message="Something unexpected happened",
        )

        extra = {
            "HTTP_AUTHORIZATION": f"Token {self.user.auth_token.key}",
        }

        view = ExportViewSet.as_view({"get": "list"})
        request = self.factory.get("/export", {"xform": self.xform.pk}, **extra)
        force_authenticate(request)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("error_message", response.data[0].keys())
        self.assertEqual(
            response.data[0]["error_message"], "Something unexpected happened"
        )

    def test_export_are_downloadable_to_all_users_when_public_form(self):
        self._create_user_and_login()
        self._publish_transportation_form()
        export = self._create_export()

        user_alice = self._create_user("alice", "alice")
        # create user profile and set require_auth to false for tests
        _ = UserProfile.objects.get_or_create(user=user_alice)
        alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % user_alice.auth_token.key}
        EditorMinorRole.add(user_alice, self.xform)

        # Form permissions are ignored when downloading Export;
        # When public editors & anonymous users should be able to
        # download all exports
        data_value = "editor-minor|dataentry-minor|readonly-no-download"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)
        self.xform.shared = True
        self.xform.shared_data = True
        self.xform.save()

        # Anonymous user
        request = self.factory.get("/export")
        response = self.view(request, pk=export.pk)
        self.assertEqual(response.status_code, 200)

        # Alice user; With editor role
        request = self.factory.get("/export", **alices_extra)
        response = self.view(request, pk=export.pk)
        self.assertEqual(response.status_code, 200)

    def test_download_from_s3(self):
        """Export is downloaded from Amazon S3"""
        self._create_user_and_login()
        self._publish_transportation_form()
        export = self._create_export()
        request = self.factory.get("/export")
        force_authenticate(request, user=self.user)
        with override_settings(
            STORAGES={"default": {"BACKEND": "storages.backends.s3.S3Storage"}},
            AWS_STORAGE_BUCKET_NAME="testing",
        ):
            with mock_aws():
                response = self.view(request, pk=export.pk)
                self.assertEqual(response.status_code, 302)
            self.assertIn("response-content-disposition", response.url)
