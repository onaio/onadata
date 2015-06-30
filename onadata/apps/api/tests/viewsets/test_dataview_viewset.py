import os

from django.conf import settings

from onadata.libs.permissions import ReadOnlyRole
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet

from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet


class TestDataViewViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", "fixtures",
            "tutorial.xls")

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
                'tutorial', 'instances', 'uuid{}'.format(x), 'submission.xml')
            self._make_submission(path)
            x += 1

        self.view = DataViewViewSet.as_view({
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve'
        })

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
                          ["name", "age", "gender"])
        self.assertEquals(response.data['query'],
                          [{"column": "age", "filter": ">", "value": "20"},
                           {"column": "age", "filter": "<", "value": "50"}])
        self.assertEquals(response.data['url'],
                          'http://testserver/api/v1/dataviews/%s'
                          % self.data_view.pk)

    def test_update_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView updated",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }

        request = self.factory.put('/', data=data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], 'My DataView updated')

        self.assertEquals(response.data['columns'],
                          ["name", "age", "gender"])

        self.assertEquals(response.data['query'],
                          [{"column": "age", "filter": ">", "value": "20"}])

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
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
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

    def test_dataview_data_filter_integer(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"},'
                     '{"column":"age","filter":"<","value":"50"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 3)
        self.assertIn("_id", response.data[0])

    def test_dataview_data_filter_date(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "gender", "_submission_time"]',
            'query': '[{"column":"_submission_time",'
                     '"filter":">=","value":"2015-01-01T00:00:00"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 7)
        self.assertIn("_id", response.data[0])

    def test_dataview_data_filter_string(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "gender", "_submission_time"]',
            'query': '[{"column":"gender","filter":"<>","value":"male"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 1)

    def test_dataview_data_filter_condition(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"name","filter":"=","value":"Fred",'
                     ' "condition":"or"},'
                     '{"column":"name","filter":"=","value":"Kameli",'
                     ' "condition":"or"},'
                     '{"column":"gender","filter":"=","value":"male"}]'
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 2)
        self.assertIn("_id", response.data[0])

    def test_dataview_invalid_filter(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"name","filter":"<=>","value":"Fred",'
                     ' "condition":"or"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {'query': [u'Filter not supported']})

    def test_dataview_sql_injection(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"age","filter":"=",'
                     '"value":"1;UNION ALL SELECT NULL,version()'
                     ',NULL LIMIT 1 OFFSET 1--;"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {"detail": u"Error retrieving the data."
                                     u" Check the query parameter"})

    def test_dataview_invalid_columns(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': 'age'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {'columns': [u'No JSON object could be decoded']})

    def test_dataview_invalid_query(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["age"]',
            'query': 'age=10'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {'query': [u'No JSON object could be decoded']})

    def test_dataview_query_not_required(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s'
                        % self.project.pk,
            'columns': '["age"]',
        }

        self._create_dataview(data=data)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 8)
        self.assertIn("_id", response.data[0])
