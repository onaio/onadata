from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import\
    OrganizationProfileViewSet


class TestOrganizationProfileViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = OrganizationProfileViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    def test_orgs_list(self):
        self._org_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.company_data])

    def test_orgs_get(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {'detail': 'Expected URL keyword argument `user`.'})
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.company_data)

    def test_orgs_create(self):
        self._org_create()
