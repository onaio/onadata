# -*- coding: utf-8 -*-
"""
Test MetaData model.
"""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from onadata.apps.logger.models import DataView, Instance, Project, XForm
from onadata.apps.main.models.meta_data import MetaData, unique_type_for_form, upload_to
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.common_tags import (
    GOOGLE_SHEET_DATA_TYPE,
    GOOGLE_SHEET_ID,
    UPDATE_OR_DELETE_GOOGLE_SHEET_DATA,
    USER_ID,
)


# pylint: disable=too-many-public-methods
class TestMetaData(TestBase):
    """
    Test MetaData model.
    """

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()

    def test_create_metadata(self):
        count = len(
            MetaData.objects.filter(object_id=self.xform.id, data_type="enketo_url")
        )
        enketo_url = "https://dmfrm.enketo.org/webform"
        MetaData.enketo_url(self.xform, enketo_url)
        self.assertEqual(
            count + 1,
            len(
                MetaData.objects.filter(object_id=self.xform.id, data_type="enketo_url")
            ),
        )

    def test_create_google_sheet_metadata_object(self):
        count = len(
            MetaData.objects.filter(
                object_id=self.xform.id, data_type=GOOGLE_SHEET_DATA_TYPE
            )
        )
        google_sheets_actions = ("{} ABC100| " "{} True | " "{} 123").format(
            GOOGLE_SHEET_ID, UPDATE_OR_DELETE_GOOGLE_SHEET_DATA, USER_ID
        )
        MetaData.set_google_sheet_details(self.xform, google_sheets_actions)
        # change
        self.assertEqual(
            count + 1,
            MetaData.objects.filter(
                object_id=self.xform.id, data_type=GOOGLE_SHEET_DATA_TYPE
            ).count(),
        )

        gsheet_details = MetaData.get_google_sheet_details(self.xform.pk)
        self.assertEqual(
            {
                GOOGLE_SHEET_ID: "ABC100",
                UPDATE_OR_DELETE_GOOGLE_SHEET_DATA: "True",
                USER_ID: "123",
            },
            gsheet_details,
        )

    def test_saving_same_metadata_object_doesnt_trigger_integrity_error(self):
        count = len(
            MetaData.objects.filter(object_id=self.xform.id, data_type="enketo_url")
        )
        enketo_url = "https://dmfrm.enketo.org/webform"
        MetaData.enketo_url(self.xform, enketo_url)
        count += 1
        self.assertEqual(
            count,
            len(
                MetaData.objects.filter(object_id=self.xform.id, data_type="enketo_url")
            ),
        )

        MetaData.enketo_url(self.xform, enketo_url)
        self.assertEqual(
            count,
            len(
                MetaData.objects.filter(object_id=self.xform.id, data_type="enketo_url")
            ),
        )

    def test_unique_type_for_form(self):
        metadata = unique_type_for_form(
            self.xform,
            data_type="enketo_url",
            data_value="https://dmfrm.enketo.org/webform",
        )

        self.assertIsInstance(metadata, MetaData)

        metadata_1 = unique_type_for_form(
            self.xform,
            data_type="enketo_url",
            data_value="https://dmerm.enketo.org/webform",
        )

        self.assertIsInstance(metadata_1, MetaData)
        self.assertNotEqual(metadata.data_value, metadata_1.data_value)
        self.assertEqual(metadata.data_type, metadata_1.data_type)
        self.assertEqual(metadata.content_object, metadata_1.content_object)

    def test_upload_to_with_anonymous_user(self):
        instance = Instance(user=self.user, xform=self.xform)
        metadata = MetaData(data_type="media")
        metadata.content_object = instance
        filename = "filename"
        self.assertEqual(
            upload_to(metadata, filename),
            "{}/{}/{}".format(self.user.username, "formid-media", filename),
        )
        # test instance with anonymous user

        instance_without_user = Instance(xform=self.xform)
        metadata.content_object = instance_without_user
        self.assertEqual(
            upload_to(metadata, filename),
            "{}/{}/{}".format(self.xform.user.username, "formid-media", filename),
        )

    def test_upload_to_with_project_and_xform_instance(self):
        model_instance = Project(created_by=self.user)
        metadata = MetaData(data_type="media")
        metadata.content_object = model_instance

        filename = "filename"

        self.assertEqual(
            upload_to(metadata, filename),
            "{}/{}/{}".format(self.user.username, "formid-media", filename),
        )
        model_instance = XForm(user=self.user, created_by=self.user)
        metadata = MetaData(data_type="media")
        metadata.content_object = model_instance

        filename = "filename"

        self.assertEqual(
            upload_to(metadata, filename),
            "{}/{}/{}".format(self.user.username, "formid-media", filename),
        )

    def test_caches_cleared(self):
        """Related caches are cleared on creating or updating"""
        key_1 = f"xfs-get_xform_metadata{self.xform.pk}"
        key_2 = f"xfm-manifest-{self.xform.pk}"
        cache.set(key_1, "foo")
        cache.set(key_2, "bar")
        enketo_url = "https://dmfrm.enketo.org/webform"
        # Metadata cache is cleared if any MetaData is created
        MetaData.enketo_url(self.xform, enketo_url)

        self.assertIsNone(cache.get(key_1))
        self.assertIsNotNone(cache.get(key_2))

        # Metadata cache is cleared if any MetaData is updated
        metadata = MetaData.objects.first()
        cache.set(key_1, "foo")
        metadata.save()

        self.assertIsNone(cache.get(key_1))
        self.assertIsNotNone(cache.get(key_2))

        # Manifest cache is cleared if `media` MetaData is created
        metadata = MetaData.objects.create(data_type="media", object_id=self.xform.id)

        self.assertIsNone(cache.get(key_2))

        # Manifest cache is cleared if `media` MetaData is updated
        cache.set(key_2, "bar")
        metadata.save()

        self.assertIsNone(cache.get(key_2))

    def test_restore_deleted(self):
        """Soft deleted MetaData is restored"""
        # Create metadata and soft delete
        metadata = MetaData.objects.create(data_type="media", object_id=self.xform.id)
        metadata.soft_delete()
        metadata.refresh_from_db()

        self.assertIsNotNone(metadata.deleted_at)

        # Restore metadata
        metadata.restore()
        metadata.refresh_from_db()

        self.assertIsNone(metadata.deleted_at)

    @patch("onadata.libs.utils.export_tools.parse_request_export_options")
    @patch("onadata.libs.utils.api_export_tools.create_export_async")
    def test_generate_linked_xform_csv_export(
        self, mock_export_async, mock_parse_options
    ):
        """
        Export is generated if linked CSV dataset is created from an XForm.
        """
        mock_parse_options.return_value = {
            "show_choice_labels": False,
            "split_select_multiples": True,
            "repeat_index_tags": ("_", "_"),
            "group_delimiter": ".",
        }
        MetaData.objects.create(
            data_type="media",
            object_id=self.xform.id,
            data_value=f"xform {self.xform.pk} transportation",
            content_type=ContentType.objects.get_for_model(XForm),
        )

        args, kwargs = mock_export_async.call_args
        self.assertEqual(args[0], self.xform)
        self.assertEqual(args[1], "csv")
        self.assertEqual(kwargs["options"]["group_delimiter"], ".")
        self.assertEqual(kwargs["options"]["repeat_index_tags"], ("_", "_"))
        self.assertEqual(kwargs["options"]["show_choice_labels"], False)
        self.assertEqual(kwargs["options"]["split_select_multiples"], True)
        self.assertEqual(kwargs["options"]["dataview_pk"], False)

        mock_parse_options.assert_called_once_with(
            {
                "group_delimiter": ".",
                "repeat_index_tags": ("_", "_"),
            }
        )

    @patch("onadata.libs.utils.export_tools.parse_request_export_options")
    @patch("onadata.libs.utils.api_export_tools.create_export_async")
    def test_generate_linked_xform_geojson_export(
        self, mock_export_async, mock_parse_options
    ):
        """
        Export is generated if linked GeoJSON dataset is created from an XForm.
        """
        mock_parse_options.return_value = {
            "group_delimiter": ".",
            "repeat_index_tags": ("_", "_"),
            "show_choice_labels": False,
            "split_select_multiples": True,
        }
        MetaData.objects.create(
            data_type="media",
            object_id=self.xform.id,
            data_value=f"xform_geojson {self.xform.pk} transportation",
            extra_data={
                "data_geo_field": "geo_field_1",
                "data_simple_style": True,
                "data_title": "fruits",
                "data_fields": "field_1,field_2,field_3",
            },
        )

        args, kwargs = mock_export_async.call_args
        self.assertEqual(args[0], self.xform)
        self.assertEqual(args[1], "geojson")
        self.assertEqual(kwargs["options"]["group_delimiter"], ".")
        self.assertEqual(kwargs["options"]["repeat_index_tags"], ("_", "_"))
        self.assertEqual(kwargs["options"]["show_choice_labels"], False)
        self.assertEqual(kwargs["options"]["split_select_multiples"], True)
        self.assertEqual(kwargs["options"]["dataview_pk"], False)
        self.assertEqual(kwargs["options"]["geo_field"], "geo_field_1")
        self.assertEqual(kwargs["options"]["simple_style"], True)
        self.assertEqual(kwargs["options"]["title"], "fruits")
        self.assertEqual(kwargs["options"]["fields"], "field_1,field_2,field_3")

        mock_parse_options.assert_called_once_with(
            {
                "group_delimiter": ".",
                "repeat_index_tags": ("_", "_"),
            }
        )

    @patch("onadata.libs.utils.export_tools.parse_request_export_options")
    @patch("onadata.libs.utils.api_export_tools.create_export_async")
    def test_generate_link_data_view_csv_export(
        self, mock_export_async, mock_parse_options
    ):
        """
        Export is generated if linked CSV dataset is created from a DataView.
        """
        mock_parse_options.return_value = {
            "group_delimiter": ".",
            "repeat_index_tags": ("_", "_"),
            "show_choice_labels": False,
            "split_select_multiples": True,
        }
        data_view = DataView.objects.create(
            xform=self.xform,
            name="transportation",
            columns=["column1", "column2", "column3"],
            project=self.project,
        )
        MetaData.objects.create(
            data_type="media",
            object_id=self.xform.id,
            data_value=f"dataview {data_view.pk} transportation",
        )

        args, kwargs = mock_export_async.call_args
        self.assertEqual(args[0], self.xform)
        self.assertEqual(args[1], "csv")
        self.assertEqual(kwargs["options"]["group_delimiter"], ".")
        self.assertEqual(kwargs["options"]["repeat_index_tags"], ("_", "_"))
        self.assertEqual(kwargs["options"]["show_choice_labels"], False)
        self.assertEqual(kwargs["options"]["split_select_multiples"], True)
        self.assertEqual(kwargs["options"]["dataview_pk"], data_view.pk)

        mock_parse_options.assert_called_once_with(
            {
                "group_delimiter": ".",
                "repeat_index_tags": ("_", "_"),
            }
        )

    @patch("onadata.libs.utils.export_tools.parse_request_export_options")
    @patch("onadata.libs.utils.api_export_tools.create_export_async")
    def test_generate_link_data_view_geojson_export(
        self, mock_export_async, mock_parse_options
    ):
        """
        Export is generated if linked GeoJSON dataset is created from a DataView.
        """
        mock_parse_options.return_value = {
            "group_delimiter": ".",
            "repeat_index_tags": ("_", "_"),
            "show_choice_labels": False,
            "split_select_multiples": True,
        }
        data_view = DataView.objects.create(
            xform=self.xform,
            name="transportation",
            columns=["column1", "column2", "column3"],
            project=self.project,
        )
        MetaData.objects.create(
            data_type="media",
            object_id=self.xform.id,
            data_value=f"dataview_geojson {data_view.pk} transportation",
            content_type=ContentType.objects.get_for_model(XForm),
            extra_data={
                "data_geo_field": "geo_field_1",
                "data_simple_style": True,
                "data_title": "fruits",
                "data_fields": "field_1,field_2,field_3",
            },
        )

        args, kwargs = mock_export_async.call_args
        self.assertEqual(args[0], self.xform)
        self.assertEqual(args[1], "geojson")
        self.assertEqual(kwargs["options"]["group_delimiter"], ".")
        self.assertEqual(kwargs["options"]["repeat_index_tags"], ("_", "_"))
        self.assertEqual(kwargs["options"]["show_choice_labels"], False)
        self.assertEqual(kwargs["options"]["split_select_multiples"], True)
        self.assertEqual(kwargs["options"]["dataview_pk"], data_view.pk)
        self.assertEqual(kwargs["options"]["geo_field"], "geo_field_1")
        self.assertEqual(kwargs["options"]["simple_style"], True)
        self.assertEqual(kwargs["options"]["title"], "fruits")
        self.assertEqual(kwargs["options"]["fields"], "field_1,field_2,field_3")

        mock_parse_options.assert_called_once_with(
            {
                "group_delimiter": ".",
                "repeat_index_tags": ("_", "_"),
            }
        )

    @patch("onadata.libs.utils.api_export_tools.include_hxl_row")
    @patch("onadata.apps.main.models.meta_data.get_columns_with_hxl")
    @patch("onadata.libs.utils.export_tools.parse_request_export_options")
    @patch("onadata.libs.utils.api_export_tools.create_export_async")
    def test_generate_link_data_view_hxl_export(
        self,
        mock_export_async,
        mock_parse_options,
        mock_get_hxl_cols,
        mock_hxl_row,
    ):
        """
        Export is generated with include_hxl set to True if dataview has HXL columns.
        """
        mock_parse_options.return_value = {
            "group_delimiter": ".",
            "repeat_index_tags": ("_", "_"),
            "show_choice_labels": False,
            "split_select_multiples": True,
        }
        mock_get_hxl_cols.return_value = ["column1", "column2", "column3"]
        mock_hxl_row.return_value = True
        data_view = DataView.objects.create(
            xform=self.xform,
            name="transportation",
            columns=["column1", "column2", "column3"],
            project=self.project,
        )
        MetaData.objects.create(
            data_type="media",
            object_id=self.xform.id,
            data_value=f"dataview {data_view.pk} transportation",
        )

        _, kwargs = mock_export_async.call_args
        # include_hxl is True if the dataview has HXL columns
        self.assertEqual(kwargs["options"]["include_hxl"], True)
        mock_get_hxl_cols.assert_called_once_with(self.xform.survey.get("children"))
        mock_hxl_row.assert_called_once_with(
            data_view.columns, mock_get_hxl_cols.return_value
        )
