"""
Tests onadata.libs.pagination module
"""
from django.http.request import HttpRequest

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.pagination import generate_pagination_headers


class TestPaginationModule(TestBase):
    """
    Tests for onadata.libs.pagination module
    """

    def test_generate_pagination_headers(self):
        req = HttpRequest()
        req.META['SERVER_NAME'] = 'testserver'
        req.META['SERVER_PORT'] = '80'
        out = generate_pagination_headers(
            req, 200, 50, 1
        )
        expected_out = {
            'Link': '<http://testserver?page=2&page_size=50>; rel="next",'
                    ' <http://testserver?page=4&page_size=50>; rel="last"'
        }
        self.assertEqual(out, expected_out)

        # Test that initial query params are kept
        req.META['QUERY_STRING'] = "filter_name=davis&sort=12"
        out = generate_pagination_headers(
            req, 200, 50, 1
        )
        expected_out = {
            'Link': '<http://testserver?filter_name=davis&sort=12&page=2&'
            'page_size=50>; rel="next", <http://testserver?filter_name=davis&'
            'sort=12&page=4&page_size=50>; rel="last"'
        }
        self.assertEqual(out, expected_out)
