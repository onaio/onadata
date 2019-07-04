from django.test import RequestFactory
from unittest.mock import MagicMock
from django.db import OperationalError
from django.test import override_settings, TestCase

from .views import normal_view
from onadata.libs.utils.middleware import OperationalErrorExceptionMiddleware

@override_settings(
    ROOT_URLCONF='onadata.libs.tests.utils.middleware_exceptions.views')
class MiddlewareTestCase(TestCase):

    def test_view_raise_OperationalError_exception(self):
        """
        Tests that the request raises an Operational Error.
        This test proves that the middleware class is able to
        intercept the exceptions raised and retry making the request
        This occurs in the case that the exception 
        is an OperationalError Exception.
        """

        get_response_mock = MagicMock(return_value=MagicMock(status_code=200, content='ok'))

        request = MagicMock()
        request.session = {}
        middleware = OperationalErrorExceptionMiddleware(get_response_mock)
        response = middleware.process_exception(request, OperationalError())

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
