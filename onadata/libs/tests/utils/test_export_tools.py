# -*- coding: utf-8 -*-
"""
Test export_tools module
"""

import csv
import json
import os
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.db.models.signals import post_save
from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone

from pyxform.builder import create_survey_from_xls
from rest_framework import exceptions
from rest_framework.authtoken.models import Token
from savReaderWriter import SavWriter

from onadata.apps.api import tests as api_tests
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.logger.models import Attachment, Entity, EntityList, Instance, XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.models.meta_data import generate_linked_dataset
from onadata.apps.viewer.models.export import Export, GenericExport
from onadata.apps.viewer.models.parsed_instance import query_fields_data
from onadata.libs.serializers.merged_xform_serializer import MergedXFormSerializer
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils.api_export_tools import custom_response_handler
from onadata.libs.utils.export_builder import (
    ExportBuilder,
    encode_if_str,
    get_value_or_attachment_uri,
)
from onadata.libs.utils.export_tools import (
    check_pending_export,
    generate_attachments_zip_export,
    generate_entity_list_export,
    generate_export,
    generate_geojson_export,
    generate_kml_export,
    generate_osm_export,
    get_columns_with_hxl,
    get_query_params_from_metadata,
    get_repeat_index_tags,
    kml_export_data,
    parse_request_export_options,
    should_create_new_export,
    str_to_bool,
)


def _logger_fixture_path(*args):
    return os.path.join(settings.PROJECT_ROOT, "libs", "tests", "fixtures", *args)


class TestExportTools(TestAbstractViewSet):
    """
    Test export_tools functions.
    """

    @classmethod
    def setUpClass(cls):
        # Disable signals
        post_save.disconnect(sender=MetaData, dispatch_uid="generate_linked_dataset")

    @classmethod
    def tearDownClass(cls):
        # Re-enable signals
        post_save.connect(
            sender=MetaData,
            dispatch_uid="generate_linked_dataset",
            receiver=generate_linked_dataset,
        )

    def _create_old_export(self, xform, export_type, options):
        Export(xform=xform, export_type=export_type, options=options).save()
        self.export = Export.objects.filter(xform=xform, export_type=export_type)

    def test_encode_if_str(self):
        row = {"date": date(1899, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, "1899-09-09")

        row = {"date": date(2001, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, "2001-09-09")

        row = {"datetime": datetime(1899, 9, 9)}
        date_str = encode_if_str(row, "datetime", True)
        self.assertEqual(date_str, "1899-09-09T00:00:00")

        row = {"datetime": datetime(2001, 9, 9)}
        date_str = encode_if_str(row, "datetime", True)
        self.assertEqual(date_str, "2001-09-09T00:00:00")

        row = {"integer_value": 1}
        integer_value = encode_if_str(row, "integer_value", sav_writer=True)
        self.assertEqual(integer_value, "1")

        integer_value = encode_if_str(row, "integer_value")
        self.assertEqual(integer_value, 1)

    def test_generate_osm_export(self):
        filenames = [
            "OSMWay234134797.osm",
            "OSMWay34298972.osm",
        ]
        osm_fixtures_dir = os.path.realpath(
            os.path.join(os.path.dirname(api_tests.__file__), "fixtures", "osm")
        )
        paths = [os.path.join(osm_fixtures_dir, filename) for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, "osm.xlsx")
        combined_osm_path = os.path.join(osm_fixtures_dir, "combined.osm")
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, "instance_a.xml")
        count = Attachment.objects.filter(extension="osm").count()

        with self.captureOnCommitCallbacks(execute=True):
            # Ensure on commit callbacks are executed
            self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(Attachment.objects.filter(extension="osm").count() > count)

        options = {"extension": Attachment.OSM}

        export = generate_osm_export(
            Attachment.OSM, self.user.username, self.xform.id_string, None, options
        )
        self.assertTrue(export.is_successful)
        with open(combined_osm_path, encoding="utf-8") as f:
            osm = f.read()
            with default_storage.open(export.filepath) as f2:
                content = f2.read().decode("utf-8")
                self.assertMultiLineEqual(content.strip(), osm.strip())

        # delete submission and check that content is no longer in export
        submission = self.xform.instances.filter().first()
        submission.deleted_at = timezone.now()
        submission.save()

        export = generate_osm_export(
            Attachment.OSM, self.user.username, self.xform.id_string, None, options
        )
        self.assertTrue(export.is_successful)
        with default_storage.open(export.filepath) as f2:
            content = f2.read()
            self.assertEqual(content, b"")

    def test_generate_attachments_zip_export(self):
        filenames = [
            "OSMWay234134797.osm",
            "OSMWay34298972.osm",
        ]
        osm_fixtures_dir = os.path.realpath(
            os.path.join(os.path.dirname(api_tests.__file__), "fixtures", "osm")
        )
        paths = [os.path.join(osm_fixtures_dir, filename) for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, "osm.xlsx")
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, "instance_a.xml")
        count = Attachment.objects.filter(extension="osm").count()
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(Attachment.objects.filter(extension="osm").count() > count)

        options = {"extension": Export.ZIP_EXPORT}

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None, options
        )

        self.assertTrue(export.is_successful)

        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            self.assertTrue(os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)

        # deleted submission
        submission = self.xform.instances.filter().first()
        submission.deleted_at = timezone.now()
        submission.save()

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None, options
        )
        self.assertTrue(export.is_successful)
        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            self.assertFalse(os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)

        # Delete attachment only but not submission
        # Restore submission
        submission.deleted_at = None
        submission.save()
        # Restore 1 attachment
        attachment = Attachment.objects.first()
        attachment.deleted_at = None
        attachment.save()

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None, options
        )
        self.assertTrue(export.is_successful)
        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            if a.pk == attachment.pk:
                self.assertTrue(
                    os.path.exists(os.path.join(temp_dir, a.media_file.name))
                )
            else:
                self.assertFalse(
                    os.path.exists(os.path.join(temp_dir, a.media_file.name))
                )
        shutil.rmtree(temp_dir)

    def test_should_create_new_export(self):
        # should only create new export if filter is defined
        # Test setup
        export_type = "csv"
        options = {"group_delimiter": "."}
        self._publish_transportation_form_and_submit_instance()

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options
        )

        self.assertTrue(will_create_new_export)

        # Should generate a new export if an instance has been
        # deleted
        self.xform.instances.first().delete()
        will_create_new_export = should_create_new_export(
            self.xform, export_type, options
        )
        self.assertTrue(will_create_new_export)

    def test_should_create_export_when_submission_deleted(self):
        """
        A new export should be generated when a submission is deleted
        """
        export_type = "csv"
        self._publish_transportation_form()
        self._make_submissions()
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
        }
        submission_count = self.xform.instances.filter(deleted_at__isnull=True).count()
        self._create_old_export(self.xform, export_type, options)

        # Delete submission
        instance = self.xform.instances.first()
        instance.set_deleted(datetime.now(), self.user)
        self.assertEqual(
            submission_count - 1,
            self.xform.instances.filter(deleted_at__isnull=True).count(),
        )
        will_create_new_export = should_create_new_export(
            self.xform, export_type, options
        )

        self.assertTrue(will_create_new_export)

        self._create_old_export(self.xform, export_type, options)
        # Deleting submission via the API still triggers a new export
        # when requested
        instance_id = self.xform.instances.filter(deleted_at__isnull=True).first().id
        view = DataViewSet.as_view({"delete": "destroy"})

        token = Token.objects.get(user=self.user)
        data = {"instance_ids": [instance_id]}
        request = self.factory.delete(
            "/", data=data, HTTP_AUTHORIZATION=f"Token {token}"
        )
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            submission_count - 2,
            self.xform.instances.filter(deleted_at__isnull=True).count(),
        )

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options
        )

        self.assertTrue(will_create_new_export)

    def test_should_not_create_new_export_fn(self):
        export_type = "csv"
        self._publish_transportation_form_and_submit_instance()
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
        }
        self._create_old_export(self.xform, export_type, options)

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options
        )

        self.assertFalse(will_create_new_export)

    def test_get_query_params_from_metadata_fn(self):
        self._publish_transportation_form_and_submit_instance()
        metadata = MetaData.objects.create(
            content_type=ContentType.objects.get_for_model(XForm),
            data_type="media",
            data_value=f"xform_geojson {self.xform.id} testgeojson2",
            extra_data={
                "data_title": "start",
                "data_fields": "",
                "data_geo_field": "qn09",
            },
            object_id=self.xform.id,
        )
        self.assertEqual(
            {
                "title": "start",
                "fields": "",
                "geo_field": "qn09",
            },
            get_query_params_from_metadata(metadata),
        )

        metadata.extra_data = {
            "data_title": "start",
            "data_fields": "one,two",
            "data_geo_field": "qn09",
        }
        self.assertEqual(
            {
                "title": "start",
                "fields": "one,two",
                "geo_field": "qn09",
            },
            get_query_params_from_metadata(metadata),
        )

        metadata.extra_data = {
            "data_title": "start",
            "data_fields": "",
            "data_geo_field": "qn09",
            "data_simple_style": True,
        }
        self.assertEqual(
            {"title": "start", "fields": "", "geo_field": "qn09", "simple_style": True},
            get_query_params_from_metadata(metadata),
        )

    def test_should_not_create_new_export_when_old_exists(self):
        export_type = "geojson"
        self._publish_transportation_form_and_submit_instance()

        request = RequestFactory().get("/")
        request.user = self.user
        request.query_params = {}
        metadata = MetaData.objects.create(
            content_type=ContentType.objects.get_for_model(XForm),
            data_type="media",
            data_value=f"xform_geojson {self.xform.id} testgeojson",
            extra_data={
                "data_title": "start",
                "data_fields": "",
                "data_geo_field": "qn09",
                "data_simple_style": True,
            },
            object_id=self.xform.id,
        )
        custom_response_handler(
            request,
            self.xform,
            {},
            export_type,
            filename="testgeojson",
            dataview=False,
            metadata=metadata,
        )

        self.assertEqual(1, Export.objects.filter(xform=self.xform).count())
        export = Export.objects.get(xform=self.xform)
        expected_export_options = {
            "dataview_pk": False,
            "include_hxl": True,
            "include_images": True,
            "include_labels": False,
            "win_excel_utf8": False,
            "group_delimiter": "/",
            "include_reviews": False,
            "remove_group_name": False,
            "include_labels_only": False,
            "split_select_multiples": True,
        }
        metadata_export_options = {
            key.replace("data_", ""): value
            for key, value in metadata.extra_data.items()
            if key.startswith("data_")
        }
        expected_export_options.update(metadata_export_options)
        self.assertEqual(export.options, expected_export_options)
        custom_response_handler(
            request,
            self.xform,
            {},
            export_type,
            filename="testgeojson",
            dataview=False,
            metadata=metadata,
        )
        # we still have only one export, we didn't generate another
        self.assertEqual(1, Export.objects.filter(xform=self.xform).count())
        self.assertEqual(export.options, expected_export_options)

        # New metadata will yield a new export
        metadata = MetaData.objects.create(
            content_type=ContentType.objects.get_for_model(XForm),
            data_type="media",
            data_value=f"xform_geojson {self.xform.id} testgeojson2",
            extra_data={
                "data_title": "end",
                "data_fields": "",
                "data_geo_field": "qn09",
                "data_simple_style": True,
            },
            object_id=self.xform.id,
        )
        custom_response_handler(
            request,
            self.xform,
            {},
            export_type,
            filename="testgeojson2",
            dataview=False,
            metadata=metadata,
        )
        metadata_export_options = {
            key.replace("data_", ""): value
            for key, value in metadata.extra_data.items()
            if key.startswith("data_")
        }
        expected_export_options.update(metadata_export_options)
        # we generated a new export since the extra_data has been updated
        self.assertEqual(2, Export.objects.filter(xform=self.xform).count())
        export = Export.objects.filter(xform=self.xform).last()
        self.assertEqual(export.options, expected_export_options)

    def test_should_create_new_export_when_filter_defined(self):
        export_type = "csv"
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
        }

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)

        # Call should_create_new_export with updated options
        options["remove_group_name"] = True

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options
        )

        self.assertTrue(will_create_new_export)

    def test_get_value_or_attachment_uri(self):
        path = os.path.join(
            os.path.dirname(__file__), "fixtures", "photo_type_in_repeat_group.xlsx"
        )
        self._publish_xls_file_and_set_xform(path)

        filename = "bob/attachments/123.jpg"
        download_url = "/api/v1/files/1?filename=%s" % filename

        # used a smaller version of row because we only using _attachmets key
        row = {
            "_attachments": [
                {
                    "mimetype": "image/jpeg",
                    "medium_download_url": "%s&suffix=medium" % download_url,
                    "download_url": download_url,
                    "filename": filename,
                    "name": "123.jpg",
                    "instance": 1,
                    "small_download_url": "%s&suffix=small" % download_url,
                    "id": 1,
                    "xform": 1,
                }
            ]
        }  # yapf: disable

        # when include_images is True, you get the attachment url
        media_xpaths = ["photo"]
        attachment_list = None
        key = "photo"
        value = "123.jpg"
        val_or_url = get_value_or_attachment_uri(
            key,
            value,
            row,
            self.xform,
            media_xpaths,
            attachment_list,
            host="example.com",
        )
        self.assertTrue(val_or_url)

        current_site = Site.objects.get_current()
        url = "http://%s%s" % (current_site.domain, download_url)
        self.assertEqual(url, val_or_url)

        # when include_images is False, you get the value
        media_xpaths = []
        val_or_url = get_value_or_attachment_uri(
            key,
            value,
            row,
            self.xform,
            media_xpaths,
            attachment_list,
            host="example.com",
        )
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

        # test that when row is an empty dict, the function still returns a
        # value
        row.pop("_attachments", None)
        self.assertEqual(row, {})

        media_xpaths = ["photo"]
        val_or_url = get_value_or_attachment_uri(
            key,
            value,
            row,
            self.xform,
            media_xpaths,
            attachment_list,
            host="example.com",
        )
        self.assertTrue(val_or_url)
        self.assertEqual(value, val_or_url)

    def test_get_attachment_uri_for_filename_with_space(self):
        path = os.path.join(
            os.path.dirname(__file__), "fixtures", "photo_type_in_repeat_group.xlsx"
        )
        self._publish_xls_file_and_set_xform(path)

        filename = "bob/attachments/1_2_3.jpg"
        download_url = "/api/v1/files/1?filename=%s" % filename

        # used a smaller version of row because we only using _attachmets key
        row = {
            "_attachments": [
                {
                    "mimetype": "image/jpeg",
                    "medium_download_url": "%s&suffix=medium" % download_url,
                    "download_url": download_url,
                    "filename": filename,
                    "name": "1 2 3.jpg",
                    "instance": 1,
                    "small_download_url": "%s&suffix=small" % download_url,
                    "id": 1,
                    "xform": 1,
                }
            ]
        }  # yapf: disable

        # when include_images is True, you get the attachment url
        media_xpaths = ["photo"]
        attachment_list = None
        key = "photo"
        value = "1 2 3.jpg"
        val_or_url = get_value_or_attachment_uri(
            key,
            value,
            row,
            self.xform,
            media_xpaths,
            attachment_list,
            host="example.com",
        )

        self.assertTrue(val_or_url)

        current_site = Site.objects.get_current()
        url = "http://%s%s" % (current_site.domain, download_url)
        self.assertEqual(url, val_or_url)

    def test_parse_request_export_options(self):
        request = self.factory.get(
            "/export_async",
            data={
                "binary_select_multiples": "true",
                "do_not_split_select_multiples": "false",
                "remove_group_name": "false",
                "include_labels": "false",
                "include_labels_only": "false",
                "include_images": "false",
            },
        )

        options = parse_request_export_options(request.GET)

        self.assertEqual(options["split_select_multiples"], True)
        self.assertEqual(options["binary_select_multiples"], True)
        self.assertEqual(options["include_labels"], False)
        self.assertEqual(options["include_labels_only"], False)
        self.assertEqual(options["remove_group_name"], False)
        self.assertEqual(options["include_images"], False)

        request = self.factory.get(
            "/export_async",
            data={
                "do_not_split_select_multiples": "true",
                "remove_group_name": "true",
                "include_labels": "true",
                "include_labels_only": "true",
                "include_images": "true",
            },
        )

        options = parse_request_export_options(request.GET)

        self.assertEqual(options["split_select_multiples"], False)
        self.assertEqual(options["include_labels"], True)
        self.assertEqual(options["include_labels_only"], True)
        self.assertEqual(options["remove_group_name"], True)
        self.assertEqual(options["include_images"], True)

    def test_export_not_found(self):
        export_type = "csv"
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
        }

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)
        export = Export(xform=self.xform, export_type=export_type, options=options)
        export.save()
        export_id = export.pk

        export.delete()
        export = generate_export(export_type, self.xform, export_id, options)

        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)
        self.assertNotEqual(export_id, export.pk)

    def test_kml_export_data(self):
        """
        Test kml_export_data(id_string, user, xform=None).
        """
        kml_md = """
        | survey |
        |        | type              | name  | label |
        |        | geopoint          | gps   | GPS   |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        xform1 = self._publish_markdown(kml_md, self.user, id_string="a")
        xform2 = self._publish_markdown(kml_md, self.user, id_string="b")
        xml = '<data id="a"><gps>-1.28 36.83</gps><fruit>orange</fruit></data>'
        Instance(xform=xform1, xml=xml).save()
        xml = '<data id="b"><gps>32.85 13.04</gps><fruit>mango</fruit></data>'
        Instance(xform=xform2, xml=xml).save()
        data = {
            "xforms": [
                "http://testserver/api/v1/forms/%s" % xform1.pk,
                "http://testserver/api/v1/forms/%s" % xform2.pk,
            ],
            "name": "Merged Dataset",
            "project": "http://testserver/api/v1/projects/%s" % xform1.project.pk,
        }  # yapf: disable
        request = self.factory.post("/")
        request.user = self.user
        serializer = MergedXFormSerializer(data=data, context={"request": request})
        self.assertTrue(serializer.is_valid())
        serializer.save()
        xform = XForm.objects.filter(pk__gt=xform2.pk, is_merged_dataset=True).first()
        expected_data = [
            {
                "name": "a",
                "image_urls": [],
                "lat": -1.28,
                "table": '<table border="1"><a href="#"><img width="210" class="thumbnail" src="" alt=""></a><tr><td>GPS</td><td>-1.28 36.83</td></tr><tr><td>Fruit</td><td>orange</td></tr></table>',  # noqa pylint: disable=C0301
                "lng": 36.83,
                "id": xform1.instances.all().first().pk,
            },
            {
                "name": "b",
                "image_urls": [],
                "lat": 32.85,
                "table": '<table border="1"><a href="#"><img width="210" class="thumbnail" src="" alt=""></a><tr><td>GPS</td><td>32.85 13.04</td></tr><tr><td>Fruit</td><td>mango</td></tr></table>',  # noqa pylint: disable=C0301
                "lng": 13.04,
                "id": xform2.instances.all().first().pk,
            },
        ]  # yapf: disable
        self.assertEqual(kml_export_data(xform.id_string, xform.user), expected_data)

    def test_kml_exports(self):
        """
        Test generate_kml_export()
        """
        export_type = "kml"
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
            "extension": "kml",
        }

        self._publish_transportation_form_and_submit_instance()
        username = self.xform.user.username
        id_string = self.xform.id_string

        export = generate_kml_export(export_type, username, id_string, options=options)
        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)

        export_id = export.id

        export.delete()

        export = generate_kml_export(
            export_type, username, id_string, export_id=export_id, options=options
        )

        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)

    def test_geojson_exports(self):
        """
        Test generate_geojson_export()
        """
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        geo_md = """
        | survey |
        |        | type              | name  | label |
        |        | geopoint          | gps   | GPS   |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        xform1 = self._publish_markdown(geo_md, self.user, id_string="a")
        xml = '<data id="a"><gps>-1.28 36.83 0 0</gps><fruit>orange</fruit></data>'
        Instance(xform=xform1, xml=xml).save()
        request = self.factory.get("/", **self.extra)
        XFormSerializer(xform1, context={"request": request}).data
        xform1 = XForm.objects.get(id_string="a")
        export_type = "geojson"
        self._publish_transportation_form_and_submit_instance()
        # set metadata to xform
        data_type = "media"
        data_value = "xform_geojson {} {}".format(xform1.pk, xform1.id_string)
        extra_data = {
            "data_title": "fruit",
            "data_geo_field": "gps",
            "data_simple_style": True,
            "data_fields": "fruit,gps",
        }
        response = self._add_form_metadata(
            self.xform, data_type, data_value, extra_data=extra_data
        )
        self.assertEqual(response.status_code, 201)
        username = self.xform.user.username
        id_string = self.xform.id_string
        # get metadata instance and pass to geojson export util function
        metadata_qs = self.xform.metadata_set.filter(data_type="media")
        self.assertEqual(metadata_qs.count(), 1)
        options = {
            "extension": "geojson",
        }
        metadata_export_options = {
            key.replace("data_", ""): value
            for key, value in extra_data.items()
            if key.startswith("data_")
        }
        options.update(metadata_export_options)
        export = generate_geojson_export(
            export_type, username, id_string, options=options, xform=xform1
        )
        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)
        with default_storage.open(export.filepath) as f2:
            content = f2.read().decode("utf-8")
            geojson = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [36.83, -1.28]},
                        "properties": {
                            "fruit": "orange",
                            "gps": "-1.28 36.83 0 0",
                            "title": "orange",
                        },
                    }
                ],
            }
            content = json.loads(content)
            # remove xform and id from properties because they keep changing
            del content["features"][0]["properties"]["id"]
            del content["features"][0]["properties"]["xform"]
            self.assertEqual(content, geojson)

        export_id = export.id

        export.delete()

        export = generate_geojson_export(
            export_type,
            username,
            id_string,
            export_id=export_id,
            options=options,
            xform=xform1,
        )

        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)

    def test_geojson_export_when_submission_deleted(self):
        """
        Test generate_geojson_export() when submissions are deleted
        """
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        geo_md = """
        | survey |
        |        | type              | name  | label |
        |        | geopoint          | gps   | GPS   |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        xform1 = self._publish_markdown(geo_md, self.user, id_string="a")
        # create 2 submissions
        xml = '<data id="a"><gps>-1.28 36.83 0 0</gps><fruit>orange</fruit></data>'
        xml2 = '<data id="a"><gps>-1.26 35.99 0 0</gps><fruit>mango</fruit></data>'
        Instance(xform=xform1, xml=xml).save()
        Instance(xform=xform1, xml=xml2).save()
        request = self.factory.get("/", **self.extra)
        XFormSerializer(xform1, context={"request": request}).data
        xform1 = XForm.objects.get(id_string="a")
        export_type = "geojson"
        self._publish_transportation_form_and_submit_instance()
        # set metadata to xform
        data_type = "media"
        data_value = "xform_geojson {} {}".format(xform1.pk, xform1.id_string)
        extra_data = {
            "data_title": "fruit",
            "data_geo_field": "gps",
            "data_simple_style": True,
            "data_fields": "fruit,gps",
        }
        # test that we have 2 active submissions before submission deletion
        self.assertEqual(
            2,
            xform1.instances.filter(deleted_at__isnull=True).count(),
        )
        # delete one sumbission from xform1
        instance = xform1.instances.first()
        instance.deleted_at = timezone.now()
        instance.save()
        self.assertEqual(
            1,
            xform1.instances.filter(deleted_at__isnull=True).count(),
        )
        response = self._add_form_metadata(
            self.xform, data_type, data_value, extra_data=extra_data
        )
        self.assertEqual(response.status_code, 201)
        username = self.xform.user.username
        id_string = self.xform.id_string
        # get metadata instance and pass to geojson export util function
        metadata_qs = self.xform.metadata_set.filter(data_type="media")
        self.assertEqual(metadata_qs.count(), 1)
        options = {
            "extension": "geojson",
        }
        metadata_export_options = {
            key.replace("data_", ""): value
            for key, value in extra_data.items()
            if key.startswith("data_")
        }
        options.update(metadata_export_options)
        export = generate_geojson_export(
            export_type, username, id_string, options=options, xform=xform1
        )
        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)
        with default_storage.open(export.filepath) as f2:
            content = f2.read().decode("utf-8")
            instance = xform1.instances.last()
            # test that only the active submission is in the export
            geojson = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [35.99, -1.26]},
                        "properties": {
                            "id": instance.pk,
                            "xform": xform1.pk,
                            "fruit": "mango",
                            "gps": "-1.26 35.99 0 0",
                            "title": "mango",
                        },
                    }
                ],
            }
            self.assertEqual(len(geojson["features"]), 1)
            content = json.loads(content)
            self.assertEqual(content, geojson)

    def test_str_to_bool(self):
        self.assertTrue(str_to_bool(True))
        self.assertTrue(str_to_bool("True"))
        self.assertTrue(str_to_bool("TRUE"))
        self.assertTrue(str_to_bool("true"))
        self.assertTrue(str_to_bool("t"))
        self.assertTrue(str_to_bool("1"))
        self.assertTrue(str_to_bool(1))

        self.assertFalse(str_to_bool(False))
        self.assertFalse(str_to_bool("False"))
        self.assertFalse(str_to_bool("F"))
        self.assertFalse(str_to_bool("random"))
        self.assertFalse(str_to_bool(234))
        self.assertFalse(str_to_bool(0))
        self.assertFalse(str_to_bool("0"))

    def test_get_sav_value_labels(self):
        md = """
        | survey |
        |        | type              | name  | label |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {"fruit": {"orange": "Orange", "mango": "Mango"}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_sav_choice_list_with_missing_values(self):
        md = """
        | survey |
        |        | type              | name  | label |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  |        |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {"fruit": {"orange": "Orange", "mango": ""}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_get_sav_value_labels_multi_language(self):
        md = """
        | survey |
        |        | type              | name  | label:English | label:Swahili |
        |        | select one fruits | fruit | Fruit         | Tunda         |

        | choices |
        |         | list name | name   | label: English | label:Swahili |
        |         | fruits    | orange | Orange         | Chungwa       |
        |         | fruits    | mango  | Mango          | Maembe        |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {"fruit": {"orange": "Orange", "mango": "Mango"}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

        export_builder.data_dicionary._default_language = "Swahili"
        expected_data = {"fruit": {"orange": "Chungwa", "mango": "Maembe"}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_get_sav_value_labels_for_choice_filter(self):
        md = """
        | survey |
        |        | type              | name  | label | choice_filter |
        |        | select one fruits | fruit | Fruit | active=1      |

        | choices |
        |         | list name | name   | label  | active |
        |         | fruits    | orange | Orange | 1      |
        |         | fruits    | mango  | Mango  | 1      |
        """
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)
        expected_data = {"fruit": {"orange": "Orange", "mango": "Mango"}}
        self.assertEqual(export_builder._get_sav_value_labels(), expected_data)

    def test_sav_duplicate_columns(self):
        more_than_64_char = (
            "akjasdlsakjdkjsadlsakjgdlsagdgdgdsajdgkjdsdgsj" "adsasdasgdsahdsahdsadgsdf"
        )
        md = """
        | survey |
        |        | type           | name | label | choice_filter |
        |        | select one fts | fruit| Fruit | active=1      |
        |	     | integer	      | age  | Age   |               |
        |	     | integer	      | {}   | Resp2 |               |
        |        | begin group    | {}   | Resp  |               |
        |	     | integer	      | age  | Resp  |               |
        |	     | text 	      | name | Name  |               |
        |        | begin group    | {}   | Resp2 |               |
        |	     | integer	      | age  | Resp2 |               |
        |	     | integer	      | {}   | Resp2 |               |
        |        | end group      |      |       |               |
        |        | end group      |      |       |               |


        | choices |
        |         | list name | name   | label  | active |
        |         | fts       | orange | Orange | 1      |
        |         | fts       | mango  | Mango  | 1      |
        """
        md = md.format(
            more_than_64_char, more_than_64_char, more_than_64_char, more_than_64_char
        )
        survey = self.md_to_pyxform_survey(md)
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)

        for sec in export_builder.sections:
            sav_options = export_builder._get_sav_options(sec["elements"])
            sav_file = NamedTemporaryFile(suffix=".sav")
            # No exception is raised
            SavWriter(sav_file.name, **sav_options)

    def test_sav_special_char_columns(self):
        survey = create_survey_from_xls(_logger_fixture_path("grains/grains.xlsx"))
        export_builder = ExportBuilder()
        export_builder.TRUNCATE_GROUP_TITLE = True
        export_builder.set_survey(survey)
        export_builder.INCLUDE_LABELS = True
        export_builder.set_survey(survey)

        for sec in export_builder.sections:
            sav_options = export_builder._get_sav_options(sec["elements"])
            sav_file = NamedTemporaryFile(suffix=".sav")
            # No exception is raised
            SavWriter(sav_file.name, **sav_options)

    @override_settings(PENDING_EXPORT_TIME=1)
    def test_retrieving_pending_export(self):
        self._create_user_and_login()
        self._publish_transportation_form()

        export = Export(
            xform=self.xform,
            export_type=Export.CSV_EXPORT,
            options={},
            task_id="abcsde",
        )

        export.save()

        test_export = check_pending_export(self.xform, Export.CSV_EXPORT, {})

        self.assertEqual(export, test_export)

        test_export = check_pending_export(self.xform, Export.XLSX_EXPORT, {})

        self.assertIsNone(test_export)

        export.created_on = export.created_on - timedelta(minutes=6)
        export.save()

        test_export = check_pending_export(self.xform, Export.CSV_EXPORT, {})

        self.assertIsNone(test_export)

    def test_get_repeat_index_tags(self):
        """
        Test get_repeat_index_tags(index_tags) function.
        """
        self.assertIsNone(get_repeat_index_tags(None))

        self.assertEqual(get_repeat_index_tags("."), (".", "."))
        self.assertEqual(get_repeat_index_tags("{,}"), ("{", "}"))

        with self.assertRaises(exceptions.ParseError):
            get_repeat_index_tags("p")

    def test_generate_filtered_attachments_zip_export(self):
        """Test media zip file export filters attachments"""
        filenames = [
            "OSMWay234134797.osm",
            "OSMWay34298972.osm",
        ]
        osm_fixtures_dir = os.path.realpath(
            os.path.join(os.path.dirname(api_tests.__file__), "fixtures", "osm")
        )
        paths = [os.path.join(osm_fixtures_dir, filename) for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, "osm.xlsx")
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, "instance_a.xml")
        count = Attachment.objects.filter(extension="osm").count()
        self._make_submission_w_attachment(submission_path, paths)
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(Attachment.objects.filter(extension="osm").count() > count)

        options = {
            "extension": Export.ZIP_EXPORT,
            "query": '{"_submission_time": {"$lte": "2019-01-13T00:00:00"}}',
        }
        filter_query = options.get("query")
        instance_ids = query_fields_data(
            self.xform, fields='["_id"]', query=filter_query
        )

        export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None, options
        )

        self.assertTrue(export.is_successful)

        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        filtered_attachments = Attachment.objects.filter(
            instance__xform_id=self.xform.pk
        ).filter(instance_id__in=[i_id["_id"] for i_id in instance_ids])

        self.assertNotEqual(Attachment.objects.count(), filtered_attachments.count())

        for a in filtered_attachments:
            self.assertTrue(os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)

        # export with no query
        options.pop("query")
        export1 = generate_attachments_zip_export(
            Export.ZIP_EXPORT, self.user.username, self.xform.id_string, None, options
        )

        self.assertTrue(export1.is_successful)

        temp_dir = tempfile.mkdtemp()
        zip_file = zipfile.ZipFile(default_storage.path(export1.filepath), "r")
        zip_file.extractall(temp_dir)
        zip_file.close()

        for a in Attachment.objects.all():
            self.assertTrue(os.path.exists(os.path.join(temp_dir, a.media_file.name)))
        shutil.rmtree(temp_dir)


class GenerateExportTestCase(TestAbstractViewSet):
    """Tests for method `generate_export`"""

    def test_generate_export_entity_list(self):
        """Generate export for EntityList dataset works"""
        # Publish registration form and create "trees" Entitylist dataset
        self._publish_registration_form(self.user)
        entity_list = EntityList.objects.get(name="trees")
        Entity.objects.create(
            entity_list=entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
        Entity.objects.create(
            entity_list=entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
            uuid="614bda97-0a46-4d31-9661-736287edf7da",
            deleted_at=timezone.now(),  # deleted Entity should be ignored
        )

        export = generate_entity_list_export(entity_list)
        self.assertIsNotNone(export)
        self.assertTrue(export.is_successful)
        self.assertEqual(GenericExport.objects.count(), 1)
        export = GenericExport.objects.first()

        with open(export.full_filepath, "r") as csv_file:
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
            # Read all rows into a list
            rows = list(csv_reader)
            self.assertEqual(len(rows), 1)
            expected_row = [
                "dbee4c32-a922-451c-9df7-42f40bf78f48",
                "300cm purpleheart",
                "-1.286905 36.772845 0 0",
                "purpleheart",
                "300",
            ]
            self.assertCountEqual(rows[0], expected_row)

    def test_get_columns_with_hxl_w_entity_forms(self):
        """Test that get_columns_with_hxl() function on a form with entities."""
        xform = self._publish_registration_form(self.user)
        self.assertEqual(get_columns_with_hxl(xform.survey_elements), {})
