from django.test import TestCase
from rest_framework.settings import api_settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import APIView
from onadata.libs.exceptions import api_exception_handler
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()


class DoesNotExistErrorView(APIView):
    def get(self, request, *args, **kwargs):
        raise ObjectDoesNotExist


class TestException(TestCase):
    def setUp(self):
        self.DEFAULT_HANDLER = api_settings.EXCEPTION_HANDLER
        api_settings.EXCEPTION_HANDLER = api_exception_handler

    def tearDown(self):
        api_settings.EXCEPTION_HANDLER = self.DEFAULT_HANDLER

    def test_api_exception_handler(self):
        view = DoesNotExistErrorView.as_view()

        request = factory.get('/', content_type='application/json')
        response = view(request)

        self.assertEqual(response.data['detail'], u'Record not found.')
