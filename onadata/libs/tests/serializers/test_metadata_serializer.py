# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.metadata_serializer
"""

import io
import os

from django.core.files.uploadedfile import InMemoryUploadedFile

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer


class TestMetaDataViewSerializer(TestAbstractViewSet):
    """
    Test MetaDataSerializer
    """

    def test_data_value_is_required(self):
        """
        Test media `data_value` is required.
        """
        data = {}
        serializer = MetaDataSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["data_value"], ["This field is required."])

    def test_media_url_validation(self):
        """
        Test media `data_value` url.
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data = {
            "data_value": "http://example.com",
            "data_type": "media",
            "xform": self.xform.pk,
        }
        serializer = MetaDataSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["data_value"],
            [
                (
                    "Cannot get filename from URL %(data_value)s. URL should "
                    "include the filename e.g %(data_value)s/data.csv" % data
                )
            ],
        )

    def test_unsupported_media_files(self):
        """
        Test unsupported media files
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data_value = "sample.svg"
        path = os.path.join(os.path.dirname(__file__), "fixtures", "sample.svg")
        with open(path) as f:
            f = InMemoryUploadedFile(
                f, "media", data_value, "application/octet-stream", 2324, None
            )
            data = {
                "data_value": data_value,
                "data_file": f,
                "data_type": "media",
                "xform": self.xform.pk,
            }
            serializer = MetaDataSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertTrue(
                serializer.errors["data_file"][0].startswith(
                    "The uploaded file 'sample.svg' could not be validated."
                ),
                serializer.errors["data_file"][0],
            )

    def test_svg_media_files(self):
        """
        Test that an SVG file is rejected
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data_value = "sample.svg"
        path = os.path.join(os.path.dirname(__file__), "fixtures", "sample.svg")
        with open(path) as f:
            f = InMemoryUploadedFile(
                f, "media", data_value, "application/octet-stream", 2324, None
            )
            data = {
                "data_value": data_value,
                "data_file": f,
                "data_type": "media",
                "xform": self.xform.pk,
            }
            serializer = MetaDataSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertTrue(
                serializer.errors["data_file"][0].startswith(
                    "The uploaded file 'sample.svg' could not be validated."
                ),
                serializer.errors["data_file"][0],
            )

    def test_invalid_csv_surfaces_validation_reason(self):
        """The specific validation reason is surfaced to API clients.

        A CSV carrying a non-UTF-8 byte (0x92, a Windows-1252 smart quote)
        must be rejected with an actionable message that explains *why* it
        failed, not only the generic "could not be validated" text.
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data_value = "delivery_partner_list.csv"
        # Header row + one data cell whose middle byte (0x92) is not valid UTF-8.
        content = b"h\r\na\x92b\r\n"
        f = InMemoryUploadedFile(
            io.BytesIO(content),
            "media",
            data_value,
            "text/csv",
            len(content),
            None,
        )
        data = {
            "data_value": data_value,
            "data_file": f,
            "data_type": "media",
            "xform": self.xform.pk,
        }
        serializer = MetaDataSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        error = serializer.errors["data_file"][0]
        self.assertTrue(
            error.startswith(
                "The uploaded file 'delivery_partner_list.csv' "
                "could not be validated."
            ),
            error,
        )
        self.assertIn("CSV files must be UTF-8 encoded.", error)

    def test_geojson_media_files(self):
        """
        GeoJSON media files are accepted (used by select_one_from_file map
        widgets in ODK).
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data_value = "sample.geojson"
        path = os.path.join(os.path.dirname(__file__), "fixtures", "sample.geojson")
        with open(path, "rb") as media_fp:
            f = InMemoryUploadedFile(
                media_fp, "media", data_value, "application/geo+json", 2324, None
            )
            data = {
                "data_value": data_value,
                "data_file": f,
                "data_type": "media",
                "xform": self.xform.pk,
            }
            serializer = MetaDataSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
