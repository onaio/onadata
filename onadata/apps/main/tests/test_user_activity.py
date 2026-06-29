# -*- coding: utf-8 -*-
"""
Test user activity tracking.
"""

import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from onadata.apps.logger.models import Instance, Project, SurveyType, XForm
from onadata.apps.main.models.user_activity import (
    USER_ACTIVITY_CACHE_PREFIX,
    UserActivity,
    get_initial_last_activity,
    record_user_activity,
)
from onadata.libs.utils.middleware import ActivityTrackingMiddleware


class TestUserActivity(TestCase):
    """Test user activity tracking helpers."""

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _create_xform(self, user, id_string="activity_form"):
        project = Project.objects.create(
            name=f"{id_string}_project",
            organization=user,
            created_by=user,
        )
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "../../logger/tests/Water_Translated_2011_03_10.xml",
        )
        sample_json = (
            '{"default_language": "default", '
            '"id_string": "Water_2011_03_17", "children": '
            '[{"type": "text", "name": "location", "label": "Location"}], '
            '"name": "Water_2011_03_17", '
            '"title": "Water_2011_03_17", "type": "survey"}'
        )
        with open(fixture_path, encoding="utf-8") as fixture:
            xml = fixture.read()

        return XForm.objects.create(
            user=user,
            project=project,
            json=sample_json,
            xml=xml,
        )

    def test_user_activity_created_for_new_user(self):
        before = timezone.now()
        user = User.objects.create_user(username="alice")

        self.assertEqual(user.activity.user, user)
        self.assertGreaterEqual(user.activity.last_activity, before)
        self.assertLessEqual(user.activity.last_activity, timezone.now())

    def test_initial_last_activity_uses_instance_submitter_and_editor(self):
        old_activity = timezone.now() - timedelta(days=400)
        submission_activity = timezone.now() - timedelta(days=2)
        edit_activity = timezone.now() - timedelta(days=1)
        form_owner = User.objects.create_user(username="form-owner")
        submitter = User.objects.create_user(username="submitter")
        editor = User.objects.create_user(username="editor")
        User.objects.filter(pk__in=[form_owner.pk, submitter.pk, editor.pk]).update(
            date_joined=old_activity,
            last_login=None,
        )
        form_owner.refresh_from_db()
        submitter.refresh_from_db()
        editor.refresh_from_db()

        survey_type = SurveyType.objects.create(slug="activity-test")
        xform = self._create_xform(form_owner)
        submission_path = os.path.join(
            os.path.dirname(__file__),
            "../../logger/tests/Water_Translated_2011_03_10_2011-03-10_14-38-28.xml",
        )
        with open(submission_path, encoding="utf-8") as fixture:
            submission_xml = fixture.read()

        Instance.objects.create(
            user=submitter,
            xform=xform,
            survey_type=survey_type,
            xml=submission_xml,
            date_created=submission_activity,
            date_modified=submission_activity,
            last_edited=edit_activity,
            last_edited_by=editor,
        )

        self.assertEqual(get_initial_last_activity(form_owner), old_activity)
        self.assertEqual(get_initial_last_activity(submitter), submission_activity)
        self.assertEqual(get_initial_last_activity(editor), edit_activity)

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

    @override_settings(ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS=300)
    def test_record_user_activity_uses_cache_throttle_before_database(self):
        user = User.objects.create_user(username="cached-activity")
        old_activity = timezone.now() - timedelta(days=400)
        UserActivity.objects.filter(user=user).update(last_activity=old_activity)

        recorded_at = timezone.now()
        record_user_activity(user, when=recorded_at)

        with CaptureQueriesContext(connection) as queries:
            activity = record_user_activity(
                user, when=recorded_at + timedelta(seconds=1)
            )

        self.assertIsNone(activity)
        self.assertEqual(len(queries), 0)

    @override_settings(ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS=0)
    def test_record_user_activity_does_not_move_activity_backwards(self):
        user = User.objects.create_user(username="concurrent-activity")
        latest_activity = timezone.now()
        UserActivity.objects.filter(user=user).update(last_activity=latest_activity)

        activity = record_user_activity(
            user, when=latest_activity - timedelta(seconds=1), force=True
        )
        activity.refresh_from_db()

        self.assertEqual(activity.last_activity, latest_activity)

    @override_settings(ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS=300)
    def test_record_user_activity_clears_cache_when_update_fails(self):
        class BrokenQuerySet:
            """QuerySet stub that raises on update."""

            def update(self, **_kwargs):
                raise DatabaseError("update failed")

        user = User.objects.create_user(username="failed-activity-update")
        old_activity = timezone.now() - timedelta(days=400)
        UserActivity.objects.filter(user=user).update(last_activity=old_activity)

        with patch.object(
            UserActivity.objects, "filter", return_value=BrokenQuerySet()
        ):
            with self.assertRaises(DatabaseError):
                record_user_activity(user, when=timezone.now())

        self.assertIsNone(cache.get(f"{USER_ACTIVITY_CACHE_PREFIX}{user.pk}"))

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

    def test_database_errors_do_not_replace_response(self):
        user = User.objects.create_user(username="middleware-db-error")

        def get_response(request):
            request.user = user
            return HttpResponse("OK")

        middleware = ActivityTrackingMiddleware(get_response)

        with patch(
            "onadata.libs.utils.middleware.record_user_activity",
            side_effect=DatabaseError("activity write failed"),
        ):
            with self.assertLogs("onadata.libs.utils.middleware", level="ERROR"):
                response = middleware(self.factory.get("/api/v1/forms"))

        self.assertEqual(response.status_code, 200)
