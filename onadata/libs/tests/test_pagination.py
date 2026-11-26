"""
Tests onadata.libs.pagination module
"""

from django.http.request import HttpRequest
from django.test import SimpleTestCase

from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from onadata.apps.logger.models import Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.pagination import (
    CountFreePageNumberPagination,
    RawSQLQueryPageNumberPagination,
    StandardPageNumberPagination,
)


class TestCountFreePagination(SimpleTestCase):
    """Validate page-size defaults and bounds without a database."""

    def test_page_size_defaults_fallback_and_maximum(self):
        records = list(range(10002))
        for params, size in (
            ({}, 1000),
            ({"page_size": "invalid"}, 1000),
            ({"page_size": 0}, 1000),
            ({"page_size": -1}, 1000),
            ({"page_size": 10001}, 10000),
        ):
            with self.subTest(params=params):
                request = Request(APIRequestFactory().get("/", params))
                paginator = CountFreePageNumberPagination()
                page = paginator.paginate_queryset(records, request)
                self.assertEqual(page, records[:size])
                self.assertIn(f"page_size={size}", paginator.get_next_link())
                self.assertIsNone(paginator.get_last_page_link())

    def test_empty_first_and_later_pages(self):
        request = Request(APIRequestFactory().get("/"))
        paginator = CountFreePageNumberPagination()
        self.assertEqual(paginator.paginate_queryset([], request), [])
        self.assertEqual(paginator.generate_link_header(), {})
        request = Request(APIRequestFactory().get("/", {"page": 2}))
        with self.assertRaises(NotFound):
            CountFreePageNumberPagination().paginate_queryset([], request)


class TestPaginationModule(TestBase):
    """
    Tests for onadata.libs.pagination module
    """

    def test_generate_link_header_function(self):
        req = HttpRequest()
        req.META["SERVER_NAME"] = "testserver"
        req.META["SERVER_PORT"] = "80"
        req.META["QUERY_STRING"] = "page=1&page_size=1"
        req.GET = {"page": 1, "page_size": 1}
        self._publish_transportation_form()
        self._make_submissions()
        qs = Instance.objects.filter(xform=self.xform)
        paginator = StandardPageNumberPagination()
        paginator.paginate_queryset(qs, Request(req))
        out = paginator.generate_link_header()
        expected_out = {
            "Link": '<http://testserver?page=2&page_size=1>; rel="next",'
            ' <http://testserver?page=4&page_size=1>; rel="last"'
        }
        self.assertEqual(out, expected_out)

        # First page link is created when not on the first page
        req.META["QUERY_STRING"] = "page=2&page_size=1"
        req.GET = {"page": 2, "page_size": 1}
        paginator = StandardPageNumberPagination()
        paginator.paginate_queryset(qs, Request(req))
        out = paginator.generate_link_header()
        expected_out = {
            "Link": '<http://testserver?page_size=1>; rel="prev", '
            '<http://testserver?page=3&page_size=1>; rel="next", '
            '<http://testserver?page=4&page_size=1>; rel="last", '
            '<http://testserver?page=1&page_size=1>; rel="first"'
        }
        self.assertEqual(out, expected_out)

        # Last page link is not created on last page
        req.META["QUERY_STRING"] = "page=4&page_size=1"
        req.GET = {"page": 4, "page_size": 1}
        paginator = StandardPageNumberPagination()
        paginator.paginate_queryset(qs, Request(req))
        out = paginator.generate_link_header()
        expected_out = {
            "Link": '<http://testserver?page=3&page_size=1>; rel="prev", '
            '<http://testserver?page=1&page_size=1>; rel="first"'
        }
        self.assertEqual(out, expected_out)


class RawSQLQueryPageNumberPaginationTestCase(TestBase):
    """Tests for the  RawSQLQueryPageNumberPagination class"""

    def setUp(self):
        super().setUp()

        self.request = HttpRequest()
        self.request.method = "GET"
        self.paginator = RawSQLQueryPageNumberPagination()

    def test_offset_limit(self):
        """Returns the correct values for offset and limit"""
        # page 1
        self.request.GET = {"page": 1, "page_size": 100}
        offset, limit = self.paginator.get_offset_limit(Request(self.request), 500)
        self.assertEqual(offset, 0)
        self.assertEqual(limit, 100)
        # page 2
        self.request.GET = {"page": 2, "page_size": 100}
        offset, limit = self.paginator.get_offset_limit(Request(self.request), 500)
        self.assertEqual(offset, 100)
        self.assertEqual(limit, 100)
        # page 3
        self.request.GET = {"page": 3, "page_size": 100}
        offset, limit = self.paginator.get_offset_limit(Request(self.request), 500)
        self.assertEqual(offset, 200)
        self.assertEqual(limit, 100)
