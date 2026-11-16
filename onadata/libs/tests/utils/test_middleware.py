"""Tests for onadata.libs.utils.middleware."""

from unittest.mock import MagicMock, patch

from django.db import OperationalError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from multidb.pinning import this_thread_is_pinned, unpin_this_thread, use_master

from onadata.libs.utils.middleware import OperationalErrorMiddleware

RECOVERY_CONFLICT = OperationalError(
    "canceling statement due to conflict with recovery\n"
    "DETAIL:  User query might have needed to see row versions that must be "
    "removed.\n"
)


class OperationalErrorMiddlewareTestCase(TestCase):
    """Retrying reads after a replica recovery conflict."""

    def setUp(self):
        # Pinning is thread state that other tests in the process can leave
        # set, so start every test unpinned.
        unpin_this_thread()
        self.addCleanup(unpin_this_thread)
        capture_patcher = patch(
            "onadata.libs.utils.middleware.sentry_sdk.capture_exception"
        )
        self.capture_exception = capture_patcher.start()
        self.addCleanup(capture_patcher.stop)
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = OperationalErrorMiddleware(self.get_response)

    def test_retries_a_read_after_a_recovery_conflict(self):
        for method in ("GET", "HEAD", "OPTIONS"):
            with self.subTest(method=method):
                self.get_response.reset_mock()

                response = self.middleware.process_exception(
                    self.factory.generic(method, "/"), RECOVERY_CONFLICT
                )

                self.assertEqual(response.status_code, 200)
                self.get_response.assert_called_once()

    def test_reports_each_retry(self):
        with self.assertLogs("onadata.libs.utils.middleware", "WARNING") as logs:
            self.middleware.process_exception(
                self.factory.get("/api/v1/data/1.json?page=2"), RECOVERY_CONFLICT
            )

        self.assertEqual(len(logs.records), 1)
        self.assertIn("GET /api/v1/data/1.json", logs.output[0])
        self.assertNotIn("page=2", logs.output[0])
        self.capture_exception.assert_called_once_with(RECOVERY_CONFLICT, level="info")

    def test_retries_on_the_primary_database(self):
        pinned_during_retry = []

        def record_pinning(request):
            pinned_during_retry.append(this_thread_is_pinned())
            return HttpResponse("OK")

        self.get_response.side_effect = record_pinning
        self.assertFalse(this_thread_is_pinned())

        self.middleware.process_exception(self.factory.get("/"), RECOVERY_CONFLICT)

        self.assertEqual(pinned_during_retry, [True])
        self.assertFalse(this_thread_is_pinned())

    def test_unpins_after_a_retry_that_uses_the_primary_itself(self):
        def view_that_pins(request):
            with use_master:
                return HttpResponse("OK")

        self.get_response.side_effect = view_that_pins
        self.assertFalse(this_thread_is_pinned())

        response = self.middleware.process_exception(
            self.factory.get("/"), RECOVERY_CONFLICT
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(this_thread_is_pinned())

    def test_keeps_a_pin_set_before_the_retry(self):
        with use_master:
            response = self.middleware.process_exception(
                self.factory.get("/"), RECOVERY_CONFLICT
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(this_thread_is_pinned())

    def test_retries_every_conflicting_request(self):
        # A retry on one request must not use up the retry of the next one
        # served by the same process.
        for _ in range(3):
            response = self.middleware.process_exception(
                self.factory.get("/"), RECOVERY_CONFLICT
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(self.get_response.call_count, 3)

    def test_retries_a_request_only_once(self):
        request = self.factory.get("/")

        first = self.middleware.process_exception(request, RECOVERY_CONFLICT)
        second = self.middleware.process_exception(request, RECOVERY_CONFLICT)

        self.assertEqual(first.status_code, 200)
        self.assertIsNone(second)
        self.get_response.assert_called_once()

    def test_does_not_retry_writes(self):
        response = self.middleware.process_exception(
            self.factory.post("/", {"name": "x"}), RECOVERY_CONFLICT
        )

        self.assertIsNone(response)
        self.get_response.assert_not_called()
        self.capture_exception.assert_not_called()

    def test_does_not_retry_other_operational_errors(self):
        response = self.middleware.process_exception(
            self.factory.get("/"),
            OperationalError("server closed the connection unexpectedly"),
        )

        self.assertIsNone(response)
        self.get_response.assert_not_called()
        self.capture_exception.assert_not_called()
