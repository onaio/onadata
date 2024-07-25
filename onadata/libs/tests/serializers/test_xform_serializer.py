# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.xform_serializer
"""
from unittest.mock import MagicMock

from django.db.models import F
from django.test import TestCase
from django.utils import timezone

from onadata.apps.logger.models import EntityList
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
        self.assertEqual(serializer.get_filename(obj), "example.com")

        obj.data_value = "http://example.com/clinics.csv"
        self.assertEqual(serializer.get_filename(obj), "clinics.csv")

    # pylint: disable=C0103
    def test_get_filename_form_filtered_dataset(self):
        """
        Test get filename from data_value for a filtered dataset.
        """
        obj = MagicMock()
        serializer = XFormManifestSerializer()

        obj.data_value = "xform 1 clinics"
        self.assertEqual(serializer.get_filename(obj), "clinics.csv")

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

        obj.file_hash = "md5:b9cc8695c526f3c7aaa882234f3b9484"
        obj.data_file = ""
        self.assertNotEqual(serializer.get_hash(obj), obj.file_hash)

        # any other dataset with media files have their hashes unchanged
        obj.data_value = "an image upload.png"
        obj.data_file = "data file"
        self.assertEqual(serializer.get_hash(obj), obj.file_hash)

    def test_entity_list_last_update_time_hash(self):
        """Hash changes when EntityList last_entity_update_time changes"""
        serializer = XFormManifestSerializer()
        self._create_user_and_login()
        # Publish registration form
        self._publish_registration_form(self.user)
        # Publish follow up form
        follow_up_xform = self._publish_follow_up_form(self.user)
        entity_list = EntityList.objects.get(name="trees")
        metadata = follow_up_xform.metadata_set.get(
            data_type="media",
            data_value=f"entity_list {entity_list.pk} {entity_list.name}",
        )
        old_hash = serializer.get_hash(metadata)
        entity_list.last_entity_update_time = timezone.now()
        entity_list.save()
        new_hash = serializer.get_hash(metadata)
        self.assertNotEqual(old_hash, new_hash)

    def test_entity_list_num_entities_hash(self):
        """Hash changes when EntityList num_entities changes"""
        serializer = XFormManifestSerializer()
        self._create_user_and_login()
        # Publish registration form
        self._publish_registration_form(self.user)
        # Publish follow up form
        follow_up_xform = self._publish_follow_up_form(self.user)
        entity_list = EntityList.objects.get(name="trees")
        entity_list.last_entity_update_time = timezone.now()
        entity_list.save()
        metadata = follow_up_xform.metadata_set.get(
            data_type="media",
            data_value=f"entity_list {entity_list.pk} {entity_list.name}",
        )
        old_hash = serializer.get_hash(metadata)
        entity_list.num_entities = F("num_entities") + 1
        entity_list.save()
        new_hash = serializer.get_hash(metadata)
        self.assertNotEqual(old_hash, new_hash)
