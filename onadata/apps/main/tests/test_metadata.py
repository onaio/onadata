# -*- coding: utf-8 -*-
"""
Test MetaData model.
"""

from django.core.cache import cache

from onadata.apps.logger.models import Instance, Project, XForm
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
