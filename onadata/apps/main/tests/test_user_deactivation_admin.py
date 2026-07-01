# -*- coding: utf-8 -*-
"""
Test inactive-account lifecycle Django admin actions.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.utils import timezone

from rest_framework.authtoken.models import Token

from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.main.admin import UserDeactivationStateAdmin
from onadata.apps.main.models.user_deactivation import (
    UserDeactivationState,
    sync_user_deactivation_state,
)
from onadata.apps.main.tests.test_base import TestBase


class TestUserDeactivationStateAdmin(TestBase):
    """Test UserDeactivationState admin actions."""

    def test_reactivate_selected_users_uses_shared_lifecycle_helper(self):
        now = timezone.now()
        deactivated_user = User.objects.create_user(
            username="admin-reactivate",
            is_active=False,
        )
        deactivated_state = sync_user_deactivation_state(deactivated_user)
        deactivated_state.deactivated_at = now - timedelta(days=1)
        deactivated_state.warned_offsets = [30]
        deactivated_state.first_warning_sent_at = now - timedelta(days=31)
        deactivated_state.save(
            update_fields=[
                "deactivated_at",
                "warned_offsets",
                "first_warning_sent_at",
            ]
        )
        active_user = User.objects.create_user(username="admin-skip")
        active_state = sync_user_deactivation_state(active_user)
        Token.objects.filter(user=deactivated_user).delete()
        TempToken.objects.filter(user=deactivated_user).delete()
        request = RequestFactory().post("/")
        model_admin = UserDeactivationStateAdmin(UserDeactivationState, AdminSite())
        model_admin.message_user = Mock()
        queryset = UserDeactivationState.objects.filter(
            pk__in=[deactivated_state.pk, active_state.pk]
        )

        with patch("onadata.apps.main.admin.timezone.now", return_value=now):
            model_admin.reactivate_selected_users(request, queryset)

        deactivated_user.refresh_from_db()
        deactivated_state.refresh_from_db()
        self.assertTrue(deactivated_user.is_active)
        self.assertTrue(Token.objects.filter(user=deactivated_user).exists())
        self.assertTrue(TempToken.objects.filter(user=deactivated_user).exists())
        self.assertEqual(deactivated_state.reactivated_at, now)
        self.assertEqual(deactivated_state.warned_offsets, [])
        self.assertIsNone(deactivated_state.first_warning_sent_at)
        self.assertEqual(model_admin.message_user.call_count, 2)
        self.assertIn(
            "Reactivated 1 inactive users.",
            model_admin.message_user.call_args_list[0][0][1],
        )
        self.assertIn(
            "Skipped 1 users that were not currently deactivated.",
            model_admin.message_user.call_args_list[1][0][1],
        )
