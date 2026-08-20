# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.metadata_serializer
"""

import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import SimpleTestCase, override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer


class TestMetaDataSerializerUrls(SimpleTestCase):
    """Test metadata URL generation without database access."""

    @staticmethod
    def _uploaded_media(data_value="photo.jpg"):
        return SimpleNamespace(
            data_type="media",
            data_value=data_value,
            data_file=SimpleNamespace(
                name="alice/formid-media/random-storage-key.jpg",
                url="http://testserver/media/random-storage-key.jpg",
            ),
            data_file_type="image/jpeg",
        )

    @patch(
        "onadata.libs.serializers.metadata_serializer.get_storages_media_download_url"
    )
    @override_settings(METADATA_SIGNED_URL_EXPIRATION=7200)
    def test_uploaded_file_url_uses_sanitized_data_value(self, mock_signed_url):
        """The signer receives the safe filename and configured expiration."""
        mock_signed_url.return_value = "https://storage.example/signed"
        metadata = self._uploaded_media("../unsafe/apple.jpg\r\n")

        url = MetaDataSerializer().get_media_url(metadata)

        self.assertEqual(url, "https://storage.example/signed")
        mock_signed_url.assert_called_once_with(
            "alice/formid-media/random-storage-key.jpg",
            'inline; filename="apple.jpg"',
            "image/jpeg",
            expires_in=7200,
        )

    @patch(
        "onadata.libs.serializers.metadata_serializer.get_storages_media_download_url"
    )
    def test_uploaded_file_url_falls_back_to_storage_url(self, mock_signed_url):
        """Local and unsupported backends retain their existing storage URL."""
        mock_signed_url.return_value = None
        metadata = self._uploaded_media()

        url = MetaDataSerializer().get_media_url(metadata)

        self.assertEqual(url, metadata.data_file.url)


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
            self.assertEqual(
                serializer.errors["data_file"][0],
                "The uploaded file 'sample.svg' could not be validated.",
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
            self.assertEqual(
                serializer.errors["data_file"][0],
                "The uploaded file 'sample.svg' could not be validated.",
            )

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
