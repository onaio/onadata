# -*- coding: utf-8 -*-
"""
Test user activity tracking.
"""

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from onadata.apps.main.models.user_activity import UserActivity, record_user_activity
from onadata.libs.utils.middleware import ActivityTrackingMiddleware


class TestUserActivity(TestCase):
    """Test user activity tracking helpers."""

    def test_user_activity_created_for_new_user(self):
        before = timezone.now()
        user = User.objects.create_user(username="alice")

        self.assertEqual(user.activity.user, user)
        self.assertGreaterEqual(user.activity.last_activity, before)
        self.assertLessEqual(user.activity.last_activity, timezone.now())

    @override_settings(ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS=0)
    def test_record_user_activity_updates_last_activity(self):
        user = User.objects.create_user(username="bob")
        old_activity = timezone.now() - timedelta(days=400)
        UserActivity.objects.filter(user=user).update(last_activity=old_activity)

        recorded_at = timezone.now()
        activity = record_user_activity(user, when=recorded_at)
        activity.refresh_from_db()

        self.assertEqual(activity.last_activity, recorded_at)

    @override_settings(ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS=300)
    def test_record_user_activity_skips_recent_activity(self):
        user = User.objects.create_user(username="carol")
        recent_activity = timezone.now() - timedelta(seconds=30)
        UserActivity.objects.filter(user=user).update(last_activity=recent_activity)

        activity = record_user_activity(user, when=timezone.now())
        activity.refresh_from_db()

        self.assertEqual(activity.last_activity, recent_activity)

    def test_record_user_activity_ignores_non_user_objects(self):
        self.assertIsNone(record_user_activity("bob"))


class TestActivityTrackingMiddleware(TestCase):
    """Test request activity tracking middleware."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS=0)
    def test_records_activity_after_view_authentication_sets_user(self):
        user = User.objects.create_user(username="middleware-user")
        old_activity = timezone.now() - timedelta(days=30)
        user.activity.last_activity = old_activity
        user.activity.save(update_fields=["last_activity"])

        def get_response(request):
            request.user = user
            return HttpResponse("OK")

        middleware = ActivityTrackingMiddleware(get_response)
        response = middleware(self.factory.get("/api/v1/forms"))
        user.activity.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertGreater(user.activity.last_activity, old_activity)

    def test_does_not_record_anonymous_requests(self):
        request = self.factory.get("/api/v1/forms")
        request.user = AnonymousUser()
        middleware = ActivityTrackingMiddleware(lambda _request: HttpResponse("OK"))
        count_before = UserActivity.objects.count()

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserActivity.objects.count(), count_before)
