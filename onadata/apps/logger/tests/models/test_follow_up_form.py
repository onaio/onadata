"""Tests for module onadata.apps.logger.models.follow_up_form"""

import pytz
from datetime import datetime
from unittest.mock import patch

from django.db.utils import IntegrityError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import FollowUpForm, EntityList


class FollowUpFormTestCase(TestBase):
    """Tests for model FollowUpForm"""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.xform = self._publish_follow_up_form(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create a FollowUpForm"""
        mock_now.return_value = self.mocked_now
        form = FollowUpForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
            is_active=True,
        )
        self.assertEqual(FollowUpForm.objects.count(), 1)
        self.assertEqual(f"{form}", f"{form.xform}|trees")
        self.assertEqual(form.xform, self.xform)
        self.assertTrue(form.is_active)
        self.assertEqual(form.entity_list, self.entity_list)
        self.assertEqual(form.date_created, self.mocked_now)
        self.assertEqual(form.date_modified, self.mocked_now)

    def test_related_name(self):
        """Related names for foreign keys work"""
        FollowUpForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )
        self.assertEqual(self.entity_list.follow_up_forms.count(), 1)
        self.assertEqual(self.xform.follow_up_forms.count(), 1)

    def test_no_duplicate_entity_list_xform(self):
        """No duplicates allowed for existing entity_list and xform"""
        FollowUpForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )

        with self.assertRaises(IntegrityError):
            FollowUpForm.objects.create(
                entity_list=self.entity_list,
                xform=self.xform,
            )

    def test_optional_fields(self):
        """Defaults for optional fields correct"""
        form = FollowUpForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )
        self.assertTrue(form.is_active)
