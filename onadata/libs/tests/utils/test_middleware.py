"""Tests for onadata.libs.utils.middleware."""

from unittest.mock import MagicMock

from django.db import OperationalError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from multidb.pinning import this_thread_is_pinned

from onadata.libs.utils.middleware import OperationalErrorMiddleware

RECOVERY_CONFLICT = OperationalError(
    "canceling statement due to conflict with recovery\n"
    "DETAIL:  User query might have needed to see row versions that must be "
    "removed.\n"
)


class OperationalErrorMiddlewareTestCase(TestCase):
    """Retrying reads after a replica recovery conflict."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = OperationalErrorMiddleware(self.get_response)

    def test_retries_a_read_after_a_recovery_conflict(self):
        response = self.middleware.process_exception(
            self.factory.get("/"), RECOVERY_CONFLICT
        )

        self.assertEqual(response.status_code, 200)
        self.get_response.assert_called_once()

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

    def test_does_not_retry_other_operational_errors(self):
        response = self.middleware.process_exception(
            self.factory.get("/"),
            OperationalError("server closed the connection unexpectedly"),
        )

        self.assertIsNone(response)
        self.get_response.assert_not_called()
