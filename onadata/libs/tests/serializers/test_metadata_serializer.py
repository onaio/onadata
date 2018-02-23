# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.metadata_serializer
"""
import os
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test.utils import override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
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
        self.assertEqual(serializer.errors['data_value'],
                         [u'This field is required.'])

    def test_media_url_validation(self):
        """
        Test media `data_value` url.
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data = {
            'data_value': 'http://example.com',
            'data_type': 'media',
            'xform': self.xform.pk
        }
        serializer = MetaDataSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors['data_value'],
            [(u"Cannot get filename from URL %(data_value)s. URL should "
              u"include the filename e.g %(data_value)s/data.csv" % data)])

    @override_settings(SUPPORTED_MEDIA_UPLOAD_TYPES=[])
    def test_unsupported_media_files(self):
        """
        Test unsupported media files
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data_value = 'sample.svg'
        path = os.path.join(os.path.dirname(__file__), 'fixtures',
                            'sample.svg')
        with open(path) as f:
            f = InMemoryUploadedFile(
                f, 'media', data_value, 'application/octet-stream', 2324, None)
            data = {
                'data_value': data_value,
                'data_file': f,
                'data_type': 'media',
                'xform': self.xform.pk
            }
            serializer = MetaDataSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertEqual(serializer.errors['data_file'],
                             [("Unsupported media file type image/svg+xml")])

    def test_svg_media_files(self):
        """
        Test that an SVG file is uploaded
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data_value = 'sample.svg'
        path = os.path.join(os.path.dirname(__file__), 'fixtures',
                            'sample.svg')
        with open(path) as f:
            f = InMemoryUploadedFile(
                f, 'media', data_value, 'application/octet-stream', 2324, None)
            data = {
                'data_value': data_value,
                'data_file': f,
                'data_type': 'media',
                'xform': self.xform.pk
            }
            serializer = MetaDataSerializer(data=data)
            self.assertTrue(serializer.is_valid())
            self.assertEquals(serializer.validated_data['data_file_type'],
                              'image/svg+xml')
