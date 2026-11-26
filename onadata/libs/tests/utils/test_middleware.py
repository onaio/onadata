"""Tests for onadata.libs.utils.middleware."""

from unittest.mock import MagicMock, patch

from django.core.signals import request_started
from django.db import OperationalError, close_old_connections
from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, SimpleTestCase

from multidb.middleware import PinningRouterMiddleware
from multidb.pinning import this_thread_is_pinned, unpin_this_thread, use_master

from onadata.libs.test_utils.recovery_conflict import recovery_conflict
from onadata.libs.utils.middleware import (
    OperationalErrorMiddleware,
    release_retry_pin,
)

RECOVERY_CONFLICT = recovery_conflict()


class OperationalErrorMiddlewareTestCase(SimpleTestCase):
    """Retrying reads after a replica recovery conflict."""

    def setUp(self):
        # Pinning is thread state that other tests in the process can leave
        # set, so start every test unpinned.
        release_retry_pin()
        unpin_this_thread()
        self.addCleanup(unpin_this_thread)
        self.addCleanup(release_retry_pin)
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

    def test_reports_a_retry_while_pinned(self):
        pinned_while_reporting = []
        self.capture_exception.side_effect = lambda *args, **kwargs: (
            pinned_while_reporting.append(this_thread_is_pinned())
        )
        self.assertFalse(this_thread_is_pinned())

        with self.assertLogs("onadata.libs.utils.middleware", "WARNING") as logs:
            self.middleware.process_exception(
                self.factory.get("/api/v1/data/1.json?page=2"), RECOVERY_CONFLICT
            )

        self.assertEqual(len(logs.records), 1)
        self.assertIn("GET '/api/v1/data/1.json'", logs.output[0])
        self.assertNotIn("page=2", logs.output[0])
        self.capture_exception.assert_called_once_with(RECOVERY_CONFLICT, level="info")
        self.assertEqual(pinned_while_reporting, [True])

    def test_escapes_the_logged_path(self):
        with self.assertLogs("onadata.libs.utils.middleware", "WARNING") as logs:
            self.middleware.process_exception(
                self.factory.get("/forged%0AERROR"), RECOVERY_CONFLICT
            )

        self.assertNotIn("\n", logs.records[0].getMessage())

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

    def test_keeps_a_streamed_retry_on_the_primary_until_it_is_read(self):
        def stream():
            yield str(this_thread_is_pinned()).encode()

        self.get_response.side_effect = lambda request: StreamingHttpResponse(stream())
        self.assertFalse(this_thread_is_pinned())

        response = self.middleware.process_exception(
            self.factory.get("/"), RECOVERY_CONFLICT
        )

        self.assertTrue(this_thread_is_pinned())
        self.assertEqual(b"".join(response.streaming_content), b"True")
        self.assertFalse(this_thread_is_pinned())

    def test_unpins_a_streamed_retry_that_fails_partway(self):
        def stream():
            yield b"first"
            raise recovery_conflict()

        self.get_response.side_effect = lambda request: StreamingHttpResponse(stream())

        response = self.middleware.process_exception(
            self.factory.get("/"), RECOVERY_CONFLICT
        )
        with self.assertRaises(OperationalError):
            b"".join(response.streaming_content)

        self.assertFalse(this_thread_is_pinned())

    def test_unpins_a_streamed_retry_closed_partway(self):
        self.get_response.side_effect = lambda request: StreamingHttpResponse(
            iter([b"first", b"second"])
        )

        response = self.middleware.process_exception(
            self.factory.get("/"), RECOVERY_CONFLICT
        )
        self.assertEqual(next(iter(response)), b"first")
        self.assertTrue(this_thread_is_pinned())
        response.close()

        self.assertFalse(this_thread_is_pinned())

    def test_unpins_a_streamed_retry_closed_before_reading(self):
        self.get_response.side_effect = lambda request: StreamingHttpResponse(
            iter([b"OK"])
        )

        response = self.middleware.process_exception(
            self.factory.head("/"), RECOVERY_CONFLICT
        )
        self.assertTrue(this_thread_is_pinned())
        response.close()

        self.assertFalse(this_thread_is_pinned())

    def _drop_a_streamed_retry(self):
        self.get_response.side_effect = lambda request: StreamingHttpResponse(
            iter([b"OK"])
        )
        self.middleware.process_exception(self.factory.get("/"), RECOVERY_CONFLICT)
        self.get_response.side_effect = None

    def _start_request(self, environ):
        # As the test client does, so the signal leaves the connection open.
        request_started.disconnect(close_old_connections)
        try:
            request_started.send(sender=self.__class__, environ=environ)
        finally:
            request_started.connect(close_old_connections)

    def _serve(self, request, *outer_middleware):
        """Serve ``request`` from the request_started signal onwards."""
        pinned_in_view = []

        def view(request):
            pinned_in_view.append(this_thread_is_pinned())
            return HttpResponse("OK")

        handler = OperationalErrorMiddleware(view)
        for middleware in reversed(outer_middleware):
            handler = middleware(handler)
        self._start_request(request.META)
        handler(request)
        return pinned_in_view

    def test_unpins_a_dropped_streamed_retry_before_the_next_request(self):
        self._drop_a_streamed_retry()
        self.assertTrue(this_thread_is_pinned())

        self.assertEqual(self._serve(self.factory.get("/")), [False])

    def test_next_write_stays_pinned_after_a_dropped_streamed_retry(self):
        self._drop_a_streamed_retry()

        self.assertEqual(
            self._serve(self.factory.post("/"), PinningRouterMiddleware), [True]
        )

    def test_next_request_keeps_a_pin_set_before_a_dropped_streamed_retry(self):
        with use_master:
            self._drop_a_streamed_retry()

            self._start_request({})

            self.assertTrue(this_thread_is_pinned())

    def test_a_stale_close_does_not_release_a_newer_retry_pin(self):
        self.get_response.side_effect = lambda request: StreamingHttpResponse(
            iter([b"OK"])
        )
        stale = self.middleware.process_exception(
            self.factory.get("/"), RECOVERY_CONFLICT
        )
        self._start_request({})
        self.middleware.process_exception(self.factory.get("/"), RECOVERY_CONFLICT)

        stale.close()

        self.assertTrue(this_thread_is_pinned())

    def test_unpins_when_reporting_the_retry_raises(self):
        self.capture_exception.side_effect = RuntimeError("report failed")
        self.assertFalse(this_thread_is_pinned())

        with self.assertRaises(RuntimeError):
            self.middleware.process_exception(self.factory.get("/"), RECOVERY_CONFLICT)

        self.capture_exception.assert_called_once()
        self.get_response.assert_not_called()
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
