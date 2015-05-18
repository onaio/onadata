
from onadata.libs.permissions import ReadOnlyRole
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet

from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet


class TestDataViewViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_xls_form_to_project()
        self.view = DataViewViewSet.as_view({
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve'
        })

    def _create_dataview(self, data=None):

        if data:
            data = data
        else:
            data = {
                'name': "My DataView",
                'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
                'project':  'http://testserver/api/v1/projects/%s'
                            % self.project.pk,
                'columns': '["asdasda", "asdasad"]',
                'query': '[{"sadsa":"asdasd"},{"sadsasa":"asdasdas"}]'
            }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)

        # load the created dataview
        self.data_view = DataView.objects.filter(xform=self.xform,
                                                 project=self.project)[0]

        self.assertEquals(response.data['name'], data['name'])
        self.assertEquals(response.data['xform'], data['xform'])
        self.assertEquals(response.data['project'], data['project'])
        self.assertEquals(response.data['columns'],
                          ["asdasda", "asdasad"])
        self.assertEquals(response.data['query'],
                          [{"sadsa": "asdasd"}, {"sadsasa": "asdasdas"}])
        self.assertEquals(response.data['url'],
                          'http://testserver/api/v1/dataview/%s'
                          % self.data_view.pk)

    def test_create_dataview(self):
        self._create_dataview()

    def test_get_dataview(self):
        self._create_dataview()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], 'My DataView')
        self.assertEquals(response.data['xform'],
                          'http://testserver/api/v1/forms/%s' % self.xform.pk)
        self.assertEquals(response.data['project'],
                          'http://testserver/api/v1/projects/%s'
                          % self.project.pk)
        self.assertEquals(response.data['columns'],
                          ["asdasda", "asdasad"])
        self.assertEquals(response.data['query'],
                          [{"sadsa": "asdasd"}, {"sadsasa": "asdasdas"}])
        self.assertEquals(response.data['url'],
                          'http://testserver/api/v1/dataview/%s'
                          % self.data_view.pk)

    def test_update_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView updated",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["asdasda_u", "asdasad"]',
            'query': '[{"sadsa":"asdasdu"},{"sadsasa":"asdasdas"}]'
        }

        request = self.factory.put('/', data=data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], 'My DataView updated')

        self.assertEquals(response.data['columns'],
                          ["asdasda_u", "asdasad"])

        self.assertEquals(response.data['query'],
                          [{"sadsa": "asdasdu"}, {"sadsasa": "asdasdas"}])

    def test_patch_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView updated",
        }

        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], 'My DataView updated')

    def test_delete_dataview(self):
        self._create_dataview()
        count = DataView.objects.filter(xform=self.xform,
                                        project=self.project).count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 204)

        after_count = DataView.objects.filter(xform=self.xform,
                                              project=self.project).count()
        self.assertEquals(count-1, after_count)

    def test_list_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["asdasda", "asdasad"]',
            'query': '[{"sadsa":"asdasd"},{"sadsasa":"asdasdas"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'list',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 2)

    def test_get_dataview_no_perms(self):
        self._create_dataview()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 404)

        # assign alice the perms
        ReadOnlyRole.add(self.user, self.data_view.project)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
