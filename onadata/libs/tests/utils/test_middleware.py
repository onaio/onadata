from unittest.mock import MagicMock

from django.conf.urls import url
from django.db import OperationalError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from onadata.libs.utils.middleware import OperationalErrorMiddleware


def normal_view(request):
    return HttpResponse('OK')


urlpatterns = [
    url('middleware_exceptions/view/', normal_view, name='normal'),
]


class MiddlewareTestCase(TestCase):

    def test_view_raise_OperationalError_exception(self):
        """
        Tests that the request raises an Operational Error.
        This test proves that the middleware class is able to
        intercept the exceptions raised and retry making the request
        """

        get_response_mock = MagicMock(
            return_value=MagicMock(status_code=200, content='ok'))

        request = MagicMock()
        request.session = {}
        middleware = OperationalErrorMiddleware(get_response_mock)
        response = middleware.process_exception(request, OperationalError(
            "canceling statement due to conflict with recovery"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_response_mock.call_count, 1)
        self.assertTrue(get_response_mock.called)

    def test_view_without_exceptions(self):

        """
        Tests that requests without exceptions are handled normally
        and do not affect the normal runnings of the middleware class.
        """
        self.factory = RequestFactory()

        request = self.factory.get('/middleware_exceptions/view/')
        view = normal_view
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'OK')
