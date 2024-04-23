from django.urls import resolve
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet

from onadata.apps.api.urls.v1_urls import router as v1_router
from onadata.apps.api.urls.v2_urls import router as v2_router


class TestOnaApi(TestAbstractViewSet):
    def test_number_of_v1_viewsets(self):
        """
        Counts the number of v1 viewsets
        for the api django app
        """
        view = v1_router.get_api_root_view()
        path = "/api/v1/"
        request = self.factory.get(path)
        request.resolver_match = resolve(path)
        response = view(request)
        self.assertEqual(len(response.data), 30)

    def test_number_of_v2_viewsets(self):
        """
        Counts the number of v2 viewsets
        for the api django app
        """
        view = v2_router.get_api_root_view()
        path = "/api/v2/"
        request = self.factory.get(path)
        request.resolver_match = resolve(path)
        response = view(request)
        self.assertEqual(len(response.data), 2)
