# -*- coding: utf-8 -*-
"""
Tests the MetaDataViewSet.
"""

# pylint: disable=too-many-lines
import os
from builtins import open
from unittest.mock import patch

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.test import override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.permissions import (
    DataEntryOnlyRole,
    DataEntryRole,
    EditorMinorRole,
    EditorRole,
)
from onadata.libs.serializers.metadata_serializer import UNIQUE_TOGETHER_ERROR
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils.common_tags import XFORM_META_PERMS


class TestMetaDataViewSet(TestAbstractViewSet):
    """
    Tests the MetaDataViewSet.
    """

    def setUp(self):
        super(TestMetaDataViewSet, self).setUp()
        self.view = MetaDataViewSet.as_view(
            {"delete": "destroy", "get": "retrieve", "post": "create"}
        )
        self._publish_xls_form_to_project()
        self.data_value = "screenshot.png"
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures", "transportation"
        )
        self.path = os.path.join(self.fixture_dir, self.data_value)

        ContentType.objects.get_or_create(app_label="logger", model="project")
        ContentType.objects.get_or_create(app_label="logger", model="instance")

    def _add_project_metadata(self, project, data_type, data_value, path=None):
        data = {"data_type": data_type, "data_value": data_value, "project": project.id}

        if path and data_value:
            with open(path, "rb") as media_file:
                data.update(
                    {
                        "data_file": media_file,
                    }
                )
                return self._post_metadata(data)
        else:
            return self._post_metadata(data)

    def _add_instance_metadata(self, data_type, data_value, path=None):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "logger",
            "fixtures",
            "tutorial",
            "tutorial.xlsx",
        )

        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        xml_submission_file_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "logger",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53.xml",
        )

        self._make_submission(xml_submission_file_path, username=self.user.username)
        self.xform.refresh_from_db()
        self.instance = self.xform.instances.first()

        data = {
            "data_type": data_type,
            "data_value": data_value,
            "instance": self.instance.id,
        }

        if path and data_value:
            with open(path, "rb") as media_file:
                data.update(
                    {
                        "data_file": media_file,
                    }
                )
                self._post_metadata(data)
        else:
            self._post_metadata(data)

    def test_add_metadata_with_file_attachment(self):
        for data_type in ["supporting_doc", "media", "source"]:
            self._add_form_metadata(self.xform, data_type, self.data_value, self.path)

    def test_parse_error_is_raised(self):
        """Parse error is raised when duplicate media is uploaded"""
        data_type = "supporting_doc"

        self._add_form_metadata(self.xform, data_type, self.data_value, self.path)
        # Duplicate upload
        response = self._add_form_metadata(
            self.xform, data_type, self.data_value, self.path, False
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(UNIQUE_TOGETHER_ERROR, response.data)

    def test_forms_endpoint_with_metadata(self):
        date_modified = self.xform.date_modified
        for data_type in ["supporting_doc", "media", "source"]:
            self._add_form_metadata(self.xform, data_type, self.data_value, self.path)
            self.xform.refresh_from_db()
            self.assertNotEqual(date_modified, self.xform.date_modified)

        # /forms
        view = XFormViewSet.as_view({"get": "retrieve"})
        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = XFormSerializer(self.xform, context={"request": request}).data
        self.assertEqual(response.data, data)

        # /projects/[pk]/forms
        view = ProjectViewSet.as_view({"get": "forms"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [data])

    @patch("onadata.libs.serializers.metadata_serializer.is_azure_storage")
    @patch("azure.storage.blob.generate_blob_sas")
    def test_forms_endpoint_with_metadata_and_azure_storage(
        self, mock_generate_blob_sas, mock_is_azure_storage
    ):
        sas_token = "sc=date+randomText"
        mock_is_azure_storage.return_value = True
        mock_generate_blob_sas.return_value = sas_token

        self._add_form_metadata(self.xform, "media", self.data_value, self.path)
        self.xform.refresh_from_db()

        # /forms
        view = XFormViewSet.as_view({"get": "retrieve"})
        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = XFormSerializer(self.xform, context={"request": request}).data
        self.assertEqual(response.data, data)
        self.assertIn(f"?{sas_token}", str(data))

    def test_get_metadata_with_file_attachment(self):
        for data_type in ["supporting_doc", "media", "source"]:
            self._add_form_metadata(self.xform, data_type, self.data_value, self.path)
            request = self.factory.get("/", **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertNotEqual(response.get("Cache-Control"), None)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.metadata_data)
            ext = self.data_value[self.data_value.rindex(".") + 1 :]
            request = self.factory.get("/", **self.extra)
            response = self.view(request, pk=self.metadata.pk, format=ext)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")

    def test_get_metadata(self):
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "transportation",
            "instances",
            "transport_2011-07-25_19-05-49",
        )
        self.data_value = "1335783522563.jpg"
        self.path = os.path.join(self.fixture_dir, self.data_value)

        self._add_form_metadata(self.xform, "media", self.data_value, self.path)
        stored_basename = os.path.basename(self.metadata.data_file.name)
        media_path_prefix = (
            f"http://localhost:8000/media/{self.user.username}/formid-media/"
        )
        data = {
            "id": self.metadata.pk,
            "xform": self.xform.pk,
            "data_value": "1335783522563.jpg",
            "data_type": "media",
            "extra_data": None,
            "data_file": f"{media_path_prefix}{stored_basename}",
            "data_file_type": "image/jpeg",
            "media_url": f"{media_path_prefix}{stored_basename}",
            "file_hash": "md5:2ca0d22073a9b6b4ebe51368b08da60c",
            "url": "http://testserver/api/v1/metadata/%s" % self.metadata.pk,
            "date_created": self.metadata.date_created,
        }
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.metadata.pk)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(dict(response.data), data)
        # Stored basename must be a UUID, not the client-supplied name.
        self.assertNotEqual(stored_basename, "1335783522563.jpg")
        self.assertTrue(stored_basename.endswith(".jpg"))

    def test_add_mapbox_layer(self):
        data_type = "mapbox_layer"
        data_value = "test_mapbox_layer||http://0.0.0.0:8080||attribution"
        self._add_form_metadata(self.xform, data_type, data_value)

    def test_delete_metadata(self):
        for data_type in ["supporting_doc", "media", "source"]:
            count = MetaData.objects.count()
            self._add_form_metadata(self.xform, data_type, self.data_value, self.path)
            request = self.factory.delete("/", **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(count, MetaData.objects.count())

    def test_delete_xform_deletes_media_metadata(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({"get": "list"})
        data = {"xform": self.xform.pk}
        request = self.factory.get("/", data, **self.extra)
        response = self.view(request)
        meta_count = self.xform.metadata_set.all().count()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), meta_count)

        # Soft delete xform
        self.xform.soft_delete()
        # Confirm that all metadata was deleted
        response2 = self.view(request)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(response2.data), 0)
        self.assertEqual(response2.data, [])

    def test_octet_stream_csv_file_upload_to_metadata_is_accepted(self):
        """A CSV uploaded with ``application/octet-stream`` is accepted.

        Windows browsers and similar clients commonly omit a precise MIME
        type. The magic-byte/CSV parser validation still runs.
        """
        data_value = "transportation.csv"
        path = os.path.join(self.fixture_dir, data_value)
        with open(path, "rb") as f:
            uploaded = InMemoryUploadedFile(
                f, "media", data_value, "application/octet-stream", 2625, None
            )
            data = {
                "data_value": data_value,
                "data_file": uploaded,
                "data_type": "media",
                "xform": self.xform.pk,
            }
            response = self._post_metadata(data)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["data_file_type"], "text/csv")

    def test_add_media_url(self):
        data_type = "media"

        # test invalid URL
        data_value = "some thing random here"
        response = self._add_form_metadata(
            self.xform, data_type, data_value, test=False
        )
        expected_exception = {"data_value": ["Invalid url 'some thing random here'."]}
        self.assertEqual(response.data, expected_exception)

        # test valid URL
        data_value = "https://devtrac.ona.io/fieldtrips.csv"
        self._add_form_metadata(self.xform, data_type, data_value)
        request = self.factory.get("/", **self.extra)
        ext = self.data_value[self.data_value.rindex(".") + 1 :]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], data_value)

    def test_add_media_xform_link(self):
        data_type = "media"

        # test missing parameters
        data_value = "xform {}".format(self.xform.pk)
        response = self._add_form_metadata(
            self.xform, data_type, data_value, test=False
        )
        expected_exception = {
            "data_value": [
                "Expecting 'xform [xform id] [media name]' or "
                "'dataview [dataview id] [media name]' or a valid URL."
            ]
        }
        self.assertEqual(response.data, expected_exception)

        data_value = "xform {} transportation".format(self.xform.pk)
        self._add_form_metadata(self.xform, data_type, data_value)
        self.assertIsNotNone(self.metadata_data["media_url"])

        request = self.factory.get("/", **self.extra)
        ext = self.data_value[self.data_value.rindex(".") + 1 :]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            "attachment; filename=\"download.csv\"; filename*=UTF-8''transportation.csv",
        )

    def test_add_media_geojson_link(self):
        data_type = "media"
        data_value = "xform_geojson {} transportation".format(self.xform.pk)
        extra_data = {
            "data_title": "test",
            "data_simple_style": True,
            "data_geo_field": "test",
            "data_fields": "transport/available_transportation_types_to_referral_facility/ambulance",  # noqa
        }
        self._add_form_metadata(
            self.xform, data_type, data_value, extra_data=extra_data
        )
        self.assertIsNotNone(self.metadata_data["media_url"])
        request = self.factory.get("/", **self.extra)
        ext = self.data_value[self.data_value.rindex(".") + 1 :]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            "attachment; filename=\"download.geojson\"; filename*=UTF-8''transportation.geojson",
        )

    def test_add_media_dataview_link(self):
        self._create_dataview()
        data_type = "media"
        data_value = "dataview {} transportation".format(self.data_view.pk)
        self._add_form_metadata(self.xform, data_type, data_value)
        self.assertIsNotNone(self.metadata_data["media_url"])

        request = self.factory.get("/", **self.extra)
        ext = self.data_value[self.data_value.rindex(".") + 1 :]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            "attachment; filename=\"download.csv\"; filename*=UTF-8''transportation.csv",
        )

    def test_invalid_post(self):
        response = self._post_metadata({}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({"data_type": "supporting_doc"}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata(
            {"data_type": "supporting_doc", "xform": self.xform.pk}, False
        )
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata(
            {"data_type": "supporting_doc", "data_value": "supporting.doc"}, False
        )
        self.assertEqual(response.status_code, 400)

    def _add_test_metadata(self):
        for data_type in ["supporting_doc", "media", "source"]:
            self._add_form_metadata(self.xform, data_type, self.data_value, self.path)

    def test_list_metadata(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({"get": "list"})
        request = self.factory.get("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

    def test_list_metadata_for_specific_form(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({"get": "list"})
        data = {"xform": self.xform.pk}
        request = self.factory.get("/", data)
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get("/", data, **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        data["xform"] = 1234509909
        request = self.factory.get("/", data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data["xform"] = "INVALID"
        request = self.factory.get("/", data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

    def test_list_public_metadata_excludes_deleted_forms(self):
        self._add_form_metadata(
            self.xform, "supporting_doc", self.data_value, self.path
        )
        self.xform.shared_data = True
        self.xform.save()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(alice_data)

        self.view = MetaDataViewSet.as_view({"get": "list"})
        data = {"xform": self.xform.pk}
        request = self.factory.get("/", data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data)

        self.xform.soft_delete()
        request = self.factory.get("/", data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_project_metadata_has_project_field(self):
        self._add_project_metadata(
            self.project, "supporting_doc", self.data_value, self.path
        )

        # Test json of project metadata
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.metadata_data["id"])

        self.assertEqual(response.status_code, 200)

        data = dict(response.data)

        self.assertIsNotNone(data["media_url"])
        self.assertEqual(data["project"], self.metadata.object_id)

    def test_instance_metadata_has_instance_field(self):
        self._add_instance_metadata("supporting_doc", self.data_value, self.path)

        # Test json of project metadata
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.metadata_data["id"])

        self.assertEqual(response.status_code, 200)

        data = dict(response.data)

        self.assertIsNotNone(data["media_url"])
        self.assertEqual(data["instance"], self.metadata.object_id)

    def test_should_return_both_xform_and_project_metadata(self):
        # delete all existing metadata
        MetaData.objects.all().delete()
        expected_metadata_count = 2

        project_response = self._add_project_metadata(
            self.project, "media", "check.png", self.path
        )
        self.assertTrue("image/png" in project_response.data["data_file_type"])

        form_response = self._add_form_metadata(
            self.xform, "supporting_doc", "bla.png", self.path
        )
        self.assertTrue("image/png" in form_response.data["data_file_type"])

        view = MetaDataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)

        self.assertEqual(MetaData.objects.count(), expected_metadata_count)

        for record in response.data:
            if record.get("xform"):
                self.assertEqual(record.get("xform"), self.xform.id)
                self.assertIsNone(record.get("project"))
            else:
                self.assertEqual(record.get("project"), self.project.id)
                self.assertIsNone(record.get("xform"))

    def test_should_only_return_xform_metadata(self):
        # delete all existing metadata
        MetaData.objects.all().delete()

        self._add_project_metadata(self.project, "media", "check.png", self.path)

        self._add_form_metadata(self.xform, "supporting_doc", "bla.png", self.path)

        view = MetaDataViewSet.as_view({"get": "list"})
        query_data = {"xform": self.xform.id}
        request = self.factory.get("/", data=query_data, **self.extra)
        response = view(request)

        self.assertEqual(len(response.data), 1)
        self.assertIn("xform", response.data[0])
        self.assertNotIn("project", response.data[0])

    def _create_metadata_object(self):
        view = MetaDataViewSet.as_view({"post": "create"})
        with open(self.path, "rb") as media_file:
            data = {
                "data_type": "media",
                "data_value": "check.png",
                "data_file": media_file,
                "project": self.project.id,
            }
            request = self.factory.post("/", data, **self.extra)
            response = view(request)

            return response

    def test_integrity_error_is_handled(self):
        count = MetaData.objects.count()

        response = self._create_metadata_object()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(count + 1, MetaData.objects.count())

        response = self._create_metadata_object()
        self.assertEqual(response.status_code, 400)

    def test_invalid_form_metadata(self):
        view = MetaDataViewSet.as_view({"post": "create"})
        with open(self.path, "rb") as media_file:
            data = {
                "data_type": "media",
                "data_value": self.data_value,
                "xform": 999912,
                "data_file": media_file,
            }

            request = self.factory.post("/", data, **self.extra)
            response = view(request)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data, {"xform": ["XForm does not exist"]})

    def test_xform_meta_permission(self):
        view = MetaDataViewSet.as_view({"post": "create"})

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor-minor|dataentry|readonly-no-download",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        meta = MetaData.xform_meta_permission(self.xform)
        self.assertEqual(meta.data_value, response.data.get("data_value"))

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor-minors|invalid_role|readonly-no-download",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 400)
        error_line_1 = "Format must be: 'editor role' | 'dataentry role' | "
        error_line_2 = "'readonly role', or an invalid role was provided."
        self.assertEqual(
            response.data, {"non_field_errors": [error_line_1 + error_line_2]}
        )

    def test_role_update_xform_meta_perms(self):
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        EditorRole.add(alice_profile.user, self.xform)

        view = MetaDataViewSet.as_view({"post": "create", "put": "update"})

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor-minor|dataentry|readonly-no-download",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        self.assertFalse(EditorRole.user_has_role(alice_profile.user, self.xform))

        self.assertTrue(EditorMinorRole.user_has_role(alice_profile.user, self.xform))

        meta = MetaData.xform_meta_permission(self.xform)

        DataEntryRole.add(alice_profile.user, self.xform)

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor|dataentry-only|readonly-no-download",
            "xform": self.xform.pk,
        }
        request = self.factory.put("/", data, **self.extra)
        response = view(request, pk=meta.pk)

        self.assertEqual(response.status_code, 200)

        self.assertFalse(DataEntryRole.user_has_role(alice_profile.user, self.xform))

        self.assertTrue(DataEntryOnlyRole.user_has_role(alice_profile.user, self.xform))

    def test_xform_meta_perms_duplicates(self):
        view = MetaDataViewSet.as_view({"post": "create", "put": "update"})

        ct = ContentType.objects.get_for_model(self.xform)

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor-minor|dataentry|readonly-no-download",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        count = MetaData.objects.filter(
            data_type=XFORM_META_PERMS, object_id=self.xform.pk, content_type=ct.pk
        ).count()

        self.assertEqual(1, count)

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor-minor|dataentry-only|readonly-no-download",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        count = MetaData.objects.filter(
            data_type=XFORM_META_PERMS, object_id=self.xform.pk, content_type=ct.pk
        ).count()

        self.assertEqual(1, count)

        metadata = MetaData.xform_meta_permission(self.xform)
        self.assertEqual(
            metadata.data_value, "editor-minor|dataentry-only|readonly-no-download"
        )

    def test_unique_submission_review_metadata(self):
        """Don't create duplicate submission_review for a form"""
        data_type = "submission_review"
        data_value = True

        response = self._add_form_metadata(self.xform, data_type, data_value)
        # Duplicate with different Data Value

        view = MetaDataViewSet.as_view({"post": "create"})
        data = {
            "xform": response.data["xform"],
            "data_type": data_type,
            "data_value": False,
        }
        request = self.factory.post("/", data, **self.extra)
        d_response = view(request)

        self.assertEqual(d_response.status_code, 400)
        self.assertIn(UNIQUE_TOGETHER_ERROR, d_response.data)

    def _post_media_upload(self, name, content, content_type):
        view = MetaDataViewSet.as_view({"post": "create"})
        uploaded = SimpleUploadedFile(name, content, content_type=content_type)
        data = {
            "data_type": "media",
            "data_value": name,
            "xform": self.xform.id,
            "data_file": uploaded,
        }
        request = self.factory.post("/", data=data, **self.extra)
        return view(request)

    def assert_upload_validation_error(self, response, filename):
        """Assert the API returns a generic file validation error."""
        self.assertEqual(
            response.data["data_file"][0],
            f"The uploaded file '{filename}' could not be validated.",
        )

    def test_media_upload_rejects_double_extension(self):
        """A `putty.exe.png` filename is rejected and no MetaData row remains."""
        before = MetaData.objects.count()

        response = self._post_media_upload("putty.exe.png", b"MZpayload", "image/png")

        self.assertEqual(response.status_code, 400)
        self.assert_upload_validation_error(response, "putty.exe.png")
        self.assertEqual(MetaData.objects.count(), before)

    def test_media_upload_rejects_signature_mismatch(self):
        """PNG content-type with executable bytes is rejected without persistence."""
        before = MetaData.objects.count()
        before_files = MetaData.objects.exclude(data_file="").count()

        response = self._post_media_upload(
            "putty.png", b"MZ\x90\x00payload", "image/png"
        )

        self.assertEqual(response.status_code, 400)
        self.assert_upload_validation_error(response, "putty.png")
        self.assertEqual(MetaData.objects.count(), before)
        self.assertEqual(MetaData.objects.exclude(data_file="").count(), before_files)

    def test_media_upload_rejects_content_type_spoof(self):
        """A real PNG file uploaded under text/csv is rejected."""
        before = MetaData.objects.count()
        with open(self.path, "rb") as png:
            png_bytes = png.read()

        response = self._post_media_upload("data.csv", png_bytes, "text/csv")

        self.assertEqual(response.status_code, 400)
        self.assert_upload_validation_error(response, "data.csv")
        self.assertEqual(MetaData.objects.count(), before)

    def test_media_upload_stores_uuid_filename(self):
        """Accepted media uploads store a UUID-based filename, not the client name."""
        with open(self.path, "rb") as png:
            png_bytes = png.read()

        response = self._post_media_upload("screenshot.png", png_bytes, "image/png")

        self.assertEqual(response.status_code, 201, response.data)
        metadata = MetaData.objects.get(pk=response.data["id"])
        stored_name = os.path.basename(metadata.data_file.name)
        self.assertNotEqual(stored_name, "screenshot.png")
        self.assertTrue(stored_name.endswith(".png"))
        # 32 hex chars + ".png"
        self.assertEqual(len(stored_name), 32 + len(".png"))
        # Original filename is preserved as display value
        self.assertEqual(metadata.data_value, "screenshot.png")
        # Stored file actually exists in storage
        self.assertTrue(default_storage.exists(metadata.data_file.name))

    def test_media_upload_mp4_stores_uuid_filename(self):
        """An MP4 form-media upload is accepted and stored under a UUID name."""
        # Minimal valid ftyp box (size 0x18, major brand "isom").
        mp4_bytes = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"

        response = self._post_media_upload("clip.mp4", mp4_bytes, "video/mp4")

        self.assertEqual(response.status_code, 201, response.data)
        metadata = MetaData.objects.get(pk=response.data["id"])
        stored_name = os.path.basename(metadata.data_file.name)
        self.assertNotEqual(stored_name, "clip.mp4")
        self.assertTrue(stored_name.endswith(".mp4"))
        # 32 hex chars + ".mp4"
        self.assertEqual(len(stored_name), 32 + len(".mp4"))
        self.assertEqual(metadata.data_value, "clip.mp4")
        self.assertTrue(default_storage.exists(metadata.data_file.name))

    def _post_supporting_doc_upload(self, name, content, content_type):
        view = MetaDataViewSet.as_view({"post": "create"})
        uploaded = SimpleUploadedFile(name, content, content_type=content_type)
        data = {
            "data_type": "supporting_doc",
            "data_value": name,
            "xform": self.xform.id,
            "data_file": uploaded,
        }
        request = self.factory.post("/", data=data, **self.extra)
        return view(request)

    @staticmethod
    def _pdf_bytes():
        return b"%PDF-1.4\nbody\n%%EOF\n"

    def test_supporting_doc_upload_rejects_double_extension(self):
        """report.pdf.html is rejected before persistence."""
        before = MetaData.objects.count()

        response = self._post_supporting_doc_upload(
            "report.pdf.html", self._pdf_bytes(), "application/pdf"
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_upload_validation_error(response, "report.pdf.html")
        self.assertEqual(MetaData.objects.count(), before)

    def test_supporting_doc_upload_rejects_content_type_spoof(self):
        """application/pdf header with non-PDF bytes is rejected."""
        before = MetaData.objects.count()

        response = self._post_supporting_doc_upload(
            "report.pdf", b"not a pdf", "application/pdf"
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_upload_validation_error(response, "report.pdf")
        self.assertEqual(MetaData.objects.count(), before)

    def test_supporting_doc_upload_rejects_svg(self):
        """SVG is no longer in the supporting-doc allowlist."""
        before = MetaData.objects.count()

        response = self._post_supporting_doc_upload(
            "icon.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml"
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_upload_validation_error(response, "icon.svg")
        self.assertEqual(MetaData.objects.count(), before)

    def test_supporting_doc_upload_rejects_zip(self):
        """ZIP is no longer in the supporting-doc allowlist."""
        before = MetaData.objects.count()
        # Empty but structurally valid ZIP
        zip_bytes = b"PK\x05\x06" + b"\x00" * 18

        response = self._post_supporting_doc_upload(
            "archive.zip", zip_bytes, "application/zip"
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_upload_validation_error(response, "archive.zip")
        self.assertEqual(MetaData.objects.count(), before)

    def test_supporting_doc_upload_rejects_legacy_doc(self):
        """Legacy .doc (OLE) uploads are rejected."""
        before = MetaData.objects.count()

        response = self._post_supporting_doc_upload(
            "report.doc",
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1payload",
            "application/msword",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_upload_validation_error(response, "report.doc")
        self.assertEqual(MetaData.objects.count(), before)

    def test_supporting_doc_upload_stores_uuid_filename(self):
        """Accepted supporting-doc uploads store a UUID-based filename."""
        response = self._post_supporting_doc_upload(
            "report.pdf", self._pdf_bytes(), "application/pdf"
        )

        self.assertEqual(response.status_code, 201, response.data)
        metadata = MetaData.objects.get(pk=response.data["id"])
        stored_name = os.path.basename(metadata.data_file.name)
        self.assertNotEqual(stored_name, "report.pdf")
        self.assertTrue(stored_name.endswith(".pdf"))
        # 32 hex chars + ".pdf"
        self.assertEqual(len(stored_name), 32 + len(".pdf"))
        # Original filename preserved as display value
        self.assertEqual(metadata.data_value, "report.pdf")

    @override_settings(
        STRICT_UPLOAD_MAX_BYTES={"supporting_doc": {"*": 8}},
    )
    def test_supporting_doc_oversized_upload_rejected(self):
        """A supporting-doc upload over the whole-context byte cap is rejected."""
        before = MetaData.objects.count()

        response = self._post_supporting_doc_upload(
            "report.pdf", self._pdf_bytes() * 10, "application/pdf"
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_upload_validation_error(response, "report.pdf")
        self.assertEqual(MetaData.objects.count(), before)
