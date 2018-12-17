# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.xform_serializer
"""
from django.test import TestCase
from mock import MagicMock

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.serializers.xform_serializer import XFormManifestSerializer


class TestXFormManifestSerializer(TestCase, TestBase):
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

    def test_get_hash(self):
        """
        Test get hash for filtered dataset and unchanged hash for other
        media files
        """
        # create xform and make submissions
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()

        # filtered dataset hash regenerated
        obj = MagicMock()
        serializer = XFormManifestSerializer()

        obj.data_value = "xform {} test_dataset".format(self.xform.id)

        obj.file_hash = u'md5:b9cc8695c526f3c7aaa882234f3b9484'
        obj.data_file = ""
        self.assertNotEqual(serializer.get_hash(obj), obj.file_hash)

        # any other dataset with media files have their hashes unchanged
        obj.data_value = "an image upload.png"
        obj.data_file = "data file"
        self.assertEqual(serializer.get_hash(obj), obj.file_hash)
