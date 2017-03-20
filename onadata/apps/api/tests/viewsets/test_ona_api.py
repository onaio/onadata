from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet

from onadata.apps.api.urls import router


class TestOnaApi(TestAbstractViewSet):

    def test_number_of_viewsets(self):
        '''
        Counts the number of viewsets
        '''
        view = router.get_api_root_view()

        request = self.factory.get('/')
        response = view(request)
        self.assertEquals(len(response.data), 26)
