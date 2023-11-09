"""Tests for module onadata.apps.logger.models.follow_up_form"""
import os
import pytz
from datetime import datetime
from unittest.mock import patch
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import FollowUpForm, EntityList


class FollowUpFormTestCase(TestBase):
    """Tests for model FollowUpForm"""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        fixture_dir = os.path.join(self.this_directory, "fixtures", "entities")
        form_path = os.path.join(fixture_dir, "trees_follow_up.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create a FollowUpForm"""
        mock_now.return_value = self.mocked_now
        form = FollowUpForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )
        self.assertEqual(FollowUpForm.objects.count(), 1)
        self.assertEqual(f"{form}", f"{form.xform}|trees")
        self.assertEqual(form.xform, self.xform)
        self.assertEqual(form.entity_list, self.entity_list)
        self.assertEqual(form.created_at, self.mocked_now)
        self.assertEqual(form.updated_at, self.mocked_now)

    def test_related_name(self):
        """Related names for foreign keys work"""
        FollowUpForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )
        self.assertEqual(self.entity_list.follow_up_forms.count(), 1)
        self.assertEqual(self.xform.follow_up_lists.count(), 1)
