# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.xform_serializer
"""
from django.test import TestCase
from mock import MagicMock

from onadata.libs.serializers.xform_serializer import XFormManifestSerializer


class TestXFormManifestSerializer(TestCase):
    """
    Test XFormManifestSerializer
    """

    def test_get_filename_from_url(self):
        """
        Test get filename from a URL.
        """
        obj = MagicMock()
        serializer = XFormManifestSerializer()

        obj.data_value = "http://example.com/"
        self.assertEqual(serializer.get_filename(obj), 'example.com')

        obj.data_value = "http://example.com/clinics.csv"
        self.assertEqual(serializer.get_filename(obj), 'clinics.csv')

    # pylint: disable=C0103
    def test_get_filename_form_filtered_dataset(self):
        """
        Test get filename from data_value for a filtered dataset.
        """
        obj = MagicMock()
        serializer = XFormManifestSerializer()

        obj.data_value = "xform 1 clinics"
        self.assertEqual(serializer.get_filename(obj), 'clinics.csv')
