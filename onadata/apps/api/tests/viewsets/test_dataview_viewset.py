import json
import os

from django.conf import settings
from django.test.utils import override_settings
from django.core.cache import cache
from mock import patch

from onadata.libs.permissions import ReadOnlyRole
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.viewer.models.export import Export
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils.cache_tools import (
    DATAVIEW_COUNT,
    DATAVIEW_LAST_SUBMISSION_TIME,
    PROJECT_LINKED_DATAVIEWS)
from onadata.libs.utils.common_tags import EDITED
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet


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

    def test_dataview_with_attachment_field(self):
        view = DataViewViewSet.as_view({
            'get': 'data'
        })
        media_file = "test-image.png"
        attachment_file_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            media_file)
        submission_file_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            'tutorial', 'instances', 'uuid10', 'submission.xml')

        # make a submission with an attachment
        with open(attachment_file_path) as f:
            self._make_submission(submission_file_path, media_file=f)

        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            # ensure there's an attachment column(photo) in you dataview
            'columns': '["name", "age", "gender", "photo"]'
        }

        self._create_dataview(data=data)
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        for a in response.data:
            # retrieve the instance with attachment
            if a.get('photo') == media_file:
                instance_with_attachment = a

        self.assertTrue(instance_with_attachment)
        attachment_info = instance_with_attachment.get('_attachments')[0]
        self.assertEquals(u'image/png', attachment_info.get(u'mimetype'))
        self.assertEquals(
            u'%s/attachments/%s' % (self.user.username, media_file),
            attachment_info.get(u'filename'))
        self.assertEquals(response.status_code, 200)

    def test_get_dataview_form_definition(self):
        self._create_dataview()

        data = {
            "name": "tutorial",
            "title": "tutorial",
            "default_language": "default",
            "id_string": "tutorial",
            "type": "survey",
        }
        self.view = DataViewViewSet.as_view({
            'get': 'form',
        })
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)

        # JSON format
        response = self.view(request, pk=self.data_view.pk, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(data, response.data)

    def test_get_dataview_form_details(self):
        self._create_dataview()

        self.view = DataViewViewSet.as_view({
            'get': 'form_details',
        })
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)

        response = self.view(request, pk=self.data_view.pk, format='json')
        self.assertEqual(response.status_code, 200)

        self.assertIn("title", response.data)
        self.assertIn("created_by", response.data)
        self.assertIn("id_string", response.data)
        self.assertIn("metadata", response.data)

    def test_get_dataview(self):
        self._create_dataview()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['dataviewid'], self.data_view.pk)
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
        self.assertEquals(response.data['last_submission_time'],
                          '2015-03-09T13:34:05')

        # Public
        self.project.shared = True
        self.project.save()

        anon_request = self.factory.get('/')
        anon_response = self.view(anon_request, pk=self.data_view.pk)
        self.assertEquals(anon_response.status_code, 200)

        # Private
        self.project.shared = False
        self.project.save()

        anon_request = self.factory.get('/')
        anon_response = self.view(anon_request, pk=self.data_view.pk)
        self.assertEquals(anon_response.status_code, 404)

    def test_update_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView updated",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
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

        self.assertEquals(count - 1, after_count)

    def test_deleted_dataview_not_in_forms_list(self):
        self._create_dataview()
        get_form_request = self.factory.get('/', **self.extra)

        xform_serializer = XFormSerializer(
            self.xform,
            context={'request': get_form_request})

        self.assertIsNotNone(xform_serializer.data['data_views'])

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 204)

        xform_serializer = XFormSerializer(
            self.xform,
            context={'request': get_form_request})

        self.assertEquals(xform_serializer.data['data_views'], [])

    def test_list_dataview(self):
        self._create_dataview()

        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
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

        anon_request = request = self.factory.get('/')
        anon_response = view(anon_request)
        self.assertEquals(anon_response.status_code, 401)

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
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "age"]',
            'query': '[{"column":"age","filter":"=",'
                     '"value":"1;UNION ALL SELECT NULL,version()'
                     ',NULL LIMIT 1 OFFSET 1--;"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertIn('detail', response.data)

        self.assertTrue(str(response.data.get('detail'))
                        .startswith("invalid input syntax for integer"))

    def test_dataview_invalid_columns(self):
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
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
            'project': 'http://testserver/api/v1/projects/%s'
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
        self.assertIn(EDITED, response.data[0])

    def test_csv_export_dataview(self):
        self._create_dataview()
        count = Export.objects.all().count()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 1, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/csv')
        content_disposition = headers['Content-Disposition']
        filename = self.filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv')

        content = self.get_response_content(response)
        test_file_path = os.path.join(settings.PROJECT_ROOT, 'apps',
                                      'viewer', 'tests', 'fixtures',
                                      'dataview.csv')
        with open(test_file_path, 'r') as test_file:
            self.assertEqual(content, test_file.read())

    def test_csvzip_export_dataview(self):
        self._create_dataview()
        count = Export.objects.all().count()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk, format='csvzip')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 1, Export.objects.all().count())

        request = self.factory.get('/', **self.extra)
        response = view(request, pk='[invalid pk]', format='csvzip')
        self.assertEqual(response.status_code, 404)

    def test_zip_export_dataview(self):
        media_file = "test-image.png"
        attachment_file_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            media_file)
        submission_file_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
            'tutorial', 'instances', 'uuid10', 'submission.xml')

        # make a submission with an attachment
        with open(attachment_file_path) as f:
            self._make_submission(submission_file_path, media_file=f)

        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "photo"]',
            'query': '[{"column":"age","filter":"=","value":"90"}]'
        }
        self._create_dataview(data)
        count = Export.objects.all().count()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, len(response.data))

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk, format='zip')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 1, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/zip')
        content_disposition = headers['Content-Disposition']
        filename = self.filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.zip')

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch('onadata.apps.api.viewsets.dataview_viewset.AsyncResult')
    def test_export_csv_dataview_data_async(self, async_result):
        self._create_dataview()
        self._publish_xls_form_to_project()

        view = DataViewViewSet.as_view({
            'get': 'export_async',
        })

        request = self.factory.get('/', data={"format": "csv"},
                                   **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertIsNotNone(response.data)

        self.assertEqual(response.status_code, 202)
        self.assertTrue('job_uuid' in response.data)
        task_id = response.data.get('job_uuid')

        export_pk = Export.objects.all().order_by('pk').reverse()[0].pk

        # metaclass for mocking results
        job = type('AsyncResultMock', (),
                   {'state': 'SUCCESS', 'result': export_pk})
        async_result.return_value = job

        get_data = {'job_uuid': task_id}
        request = self.factory.get('/', data=get_data, **self.extra)
        response = view(request, pk=self.data_view.pk)

        self.assertIn('export_url', response.data)

        self.assertTrue(async_result.called)
        self.assertEqual(response.status_code, 202)
        export = Export.objects.get(task_id=task_id)
        self.assertTrue(export.is_successful)

    def _test_csv_export_with_hxl_support(self, columns, expected_output):
        data = {
            'name': "Hxl example dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': columns,
            'query': '[]'
        }

        self._create_dataview(data=data)

        dataview_pk = DataView.objects.last().pk

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get(
            '/', data={"format": "csv", "include_hxl": True}, **self.extra)
        response = view(request, pk=dataview_pk)

        self.assertIsNotNone(
            response.streaming_content.next(),
            expected_output
        )

    def test_csv_export_with_hxl_support(self):
        self._publish_form_with_hxl_support()
        self._test_csv_export_with_hxl_support(
            '["name"]',
            'name\nCristiano Ronaldo\nLionel Messi\n'
        )
        self._test_csv_export_with_hxl_support(
            '["age"]',
            'age\n#age,\n31\n29\n'
        )
        self._test_csv_export_with_hxl_support(
            '["age", "name"]',
            'age,name\n#age,\n31,Cristiano Ronaldo\n29,Lionel Messi\n'
        )

    def test_get_charts_data(self):
        self._create_dataview()
        self.view = DataViewViewSet.as_view({
            'get': 'charts',
        })
        data_view_data = DataView.query_data(self.data_view)

        request = self.factory.get('/charts', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        data = {'field_name': 'age'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')
        self.assertEqual(len(response.data['data']), len(data_view_data))

        data = {'field_xpath': 'age'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')
        self.assertEqual(len(response.data['data']), len(data_view_data))

    def test_get_charts_data_for_submission_time_field(self):
        self._create_dataview()
        self.view = DataViewViewSet.as_view({
            'get': 'charts',
        })

        data = {'field_name': '_submission_time'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'datetime')
        self.assertEqual(response.data['field_name'], '_submission_time')
        self.assertEqual(response.data['data_type'], 'time_based')

        data = {'field_name': '_submitted_by'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'text')
        self.assertEqual(response.data['field_name'], '_submitted_by')
        self.assertEqual(response.data['data_type'], 'categorized')

        data = {'field_name': '_duration'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], '_duration')
        self.assertEqual(response.data['data_type'], 'numeric')

    def test_get_charts_data_for_grouped_field(self):
        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender", "a_group/grouped"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }
        self._create_dataview(data)
        self.view = DataViewViewSet.as_view({
            'get': 'charts',
        })

        request = self.factory.get('/charts', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        data = {'field_name': 'grouped'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'grouped')
        self.assertEqual(response.data['data_type'], 'categorized')
        self.assertEqual(len(response.data['data']), 2)

    def test_get_charts_data_field_not_in_dataview_columns(self):

        self._create_dataview()
        self.view = DataViewViewSet.as_view({
            'get': 'charts',
        })

        data = {'field_name': 'grouped'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 404)

    def test_get_charts_data_with_empty_query(self):
        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[]'
        }
        self._create_dataview(data)
        self.view = DataViewViewSet.as_view({
            'get': 'charts',
        })
        data_view_data = DataView.query_data(self.data_view)

        request = self.factory.get('/charts', **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        data = {'field_name': 'age'}
        request = self.factory.get('/charts', data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')
        self.assertEqual(len(response.data['data']), len(data_view_data))

    def test_geopoint_dataview(self):
        # Dataview with geolocation column selected.
        # -> instances_with_geopoints= True
        data = {
            'name': "My DataView1",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender", "location"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }
        self._create_dataview(data)

        self.assertTrue(self.data_view.instances_with_geopoints)

        # Dataview with geolocation column NOT selected
        # -> instances_with_geopoints= False
        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }
        self._create_dataview(data)

        self.assertFalse(self.data_view.instances_with_geopoints)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['dataviewid'], self.data_view.pk)
        self.assertEquals(response.data['name'], 'My DataView2')
        self.assertEquals(response.data['instances_with_geopoints'], False)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertNotIn("location", response.data[0])
        self.assertNotIn("_geolocation", response.data[0])

    def test_geopoint_submission_dataview(self):
        data = {
            'name': "My DataView3",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender", "location"]',
            'query': '[{"column":"age","filter":">=","value":"87"}]'
        }
        self._create_dataview(data)

        self.assertTrue(self.data_view.instances_with_geopoints)

        # make submission with geopoint
        path = os.path.join(settings.PROJECT_ROOT, 'libs', 'tests', "utils",
                            'fixtures', 'tutorial', 'instances',
                            'uuid{}'.format(9), 'submission.xml')
        self._make_submission(path)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['dataviewid'], self.data_view.pk)
        self.assertEquals(response.data['name'], 'My DataView3')
        self.assertEquals(response.data['instances_with_geopoints'], True)

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)

        self.assertIn("location", response.data[0])
        self.assertIn("_geolocation", response.data[0])

    def test_dataview_project_cache_cleared(self):
        self._create_dataview()

        view = ProjectViewSet.as_view({
            'get': 'retrieve',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEquals(response.status_code, 200)

        cached_dataviews = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                   self.project.pk))

        self.assertIsNotNone(cached_dataviews)

        # update the dataview
        self.data_view.name = "updated name"
        self.data_view.save()

        updated_cache = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                self.project.pk))

        self.assertIsNone(updated_cache)

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEquals(response.status_code, 200)

        cached_dataviews = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                   self.project.pk))

        self.assertIsNotNone(cached_dataviews)

        self.data_view.delete()

        updated_cache = cache.get('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                                self.project.pk))
        self.assertIsNone(updated_cache)

    def test_dataview_update_refreshes_cached_data(self):
        self._create_dataview()
        cache.set('{}{}'.format(DATAVIEW_COUNT, self.data_view.xform.pk), 5)
        cache.set('{}{}'.format(DATAVIEW_LAST_SUBMISSION_TIME,
                                self.data_view.xform.pk),
                  '2015-03-09T13:34:05')
        self.data_view.name = "Updated Dataview"
        self.data_view.save()

        self.assertIsNone(
            cache.get('{}{}'.format(DATAVIEW_COUNT, self.data_view.xform.pk)))
        self.assertIsNone(cache.get('{}{}'.format(
            DATAVIEW_LAST_SUBMISSION_TIME, self.data_view.xform.pk)))

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        expected_count = 3
        expected_last_submission_time = "2015-03-09T13:34:05"

        self.assertEquals(response.data['count'], expected_count)
        self.assertEquals(response.data['last_submission_time'],
                          '2015-03-09T13:34:05')

        cache_dict = cache.get('{}{}'.format(DATAVIEW_COUNT,
                                             self.data_view.xform.pk))
        self.assertEquals(cache_dict.get(self.data_view.pk), expected_count)
        self.assertEquals(cache.get('{}{}'.format(
            DATAVIEW_LAST_SUBMISSION_TIME, self.data_view.xform.pk)),
            expected_last_submission_time)

    def test_export_dataview_not_affected_by_normal_exports(self):
        count = Export.objects.all().count()

        view = XFormViewSet.as_view({
            'get': 'retrieve',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 1, Export.objects.all().count())

        self._create_dataview()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 2, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/csv')
        content_disposition = headers['Content-Disposition']
        filename = self.filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv')

        content = self.get_response_content(response)

        # count csv headers and ensure they are three
        self.assertEqual(len(content.split('\n')[0].split(',')), 3)

    def test_matches_parent(self):
        self._create_dataview()
        self.assertFalse(self.data_view.matches_parent)
        columns = [u'name', u'age', u'gender', u'photo', u'date', u'location',
                   u'pizza_fan', u'pizza_hater', u'pizza_type',
                   u'favorite_toppings', u'test_location2.latitude',
                   u'test_location2.longitude', u'test_location.precision',
                   u'test_location2.precision', u'test_location.altitude',
                   u'test_location.latitude', u'test_location2.altitude',
                   u'test_location.longitude', u'thanks', u'a_group',
                   u'a_group/grouped', u'a_group/a_text', u'start_time',
                   u'end_time', u'today', u'imei', u'phonenumber',
                   'meta', 'meta/instanceID']
        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': json.dumps(columns),
            'query': '[{"column":"age","filter":">","value":"20"}]'
        }

        self._create_dataview(data)
        self.assertTrue(self.data_view.matches_parent)

    def test_dataview_create_data_filter_invalid_date(self):
        invalid_query = '[{"column":"_submission_time",' \
                        '"filter":">","value":"30/06/2015"}]'
        data = {
            'name': "Transportation Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "gender", "_submission_time"]',
            'query': invalid_query
        }

        view = DataViewViewSet.as_view({
            'get': 'data',
            'post': 'create',
            'patch': 'partial_update'
        })

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)

        # Confirm you cannot create an invalid dataview
        self.assertEquals(response.status_code, 400)

    def test_dataview_update_data_filter_invalid_date(self):
        invalid_query = '[{"column":"_submission_time",' \
                        '"filter":">","value":"30/06/2015"}]'
        self._create_dataview()

        data = {'query': invalid_query}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        # Confirm you cannot update an invalid dataview
        self.assertEquals(response.status_code, 400)

    def test_dataview_serializer_exception(self):
        invalid_query = [
            {"column": "_submission_time",
             "filter": ">",
             "value": "30/06/2015"}
        ]
        self._create_dataview()

        self.data_view.query = invalid_query
        self.data_view.save()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.data_view.pk)

        self.assertEquals(response.status_code, 400)

    def test_dataview_notes_added_to_data(self):
        # Create note
        view = NoteViewSet.as_view({
            'post': 'create'
        })
        comment = u"Dataview note"
        note = {'note': comment}
        data_id = self.xform.instances.all().order_by('pk')[0].pk
        note['instance'] = data_id
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.instances.count())
        response = view(request)
        self.assertEqual(response.status_code, 201)

        # Get dataview with added notes
        data = {
            'name': "My Dataview",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["age"]',
        }
        self._create_dataview(data=data)
        view = DataViewViewSet.as_view({
            'get': 'data'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data), 8)
        data_with_notes = \
            (d for d in response.data if d["_id"] == data_id).next()
        self.assertIn("_notes", data_with_notes)
        self.assertEquals([{'created_by': self.user.id,
                            'id': 1,
                            'instance_field': None,
                            'note': comment,
                            'owner': self.user.username}],
                          data_with_notes["_notes"])

    def test_sort_dataview_data(self):
        self._create_dataview()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        data = {"sort": '{"age": -1}'}
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(
            self.is_sorted_desc([r.get("age") for r in response.data]))

    def test_invalid_date_filter(self):
        view = DataViewViewSet.as_view({
            'get': 'retrieve',
            'post': 'create',
        })
        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"_submission_time","filter":">",'
                     '"value":"26-01-2016"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)

        response = view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {
                              u'non_field_errors':
                                  [u'Date value in _submission_time should be'
                                   u' yyyy-mm-ddThh:m:s or yyyy-mm-dd']
                          })

        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"_submission_time","filter":">",'
                     '"value":"26/01/2016"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)

        response = view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          {
                              u'non_field_errors':
                                  [u'Date value in _submission_time should be'
                                   u' yyyy-mm-ddThh:m:s or yyyy-mm-dd']
                          })

        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"_submission_time","filter":">",'
                     '"value":"2016-01-16T00:00:00"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)

        response = view(request)

        self.assertEquals(response.status_code, 201)

        data = {
            'name': "My DataView2",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"_submission_time","filter":">",'
                     '"value":"2016-01-16"}]'
        }

        request = self.factory.post('/', data=data, **self.extra)

        response = view(request)

        self.assertEquals(response.status_code, 201)

    def test_search_dataview_data(self):
        self._create_dataview()

        view = DataViewViewSet.as_view({
            'get': 'data',
        })

        data = {"query": "Fred"}
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)

        self.assertEqual(1, len(response.data))
        self.assertEqual("Fred", response.data[0].get('name'))

        data = {"query": '{"age": 22}'}
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)

        self.assertEqual(1, len(response.data))
        self.assertEqual(22, response.data[0].get('age'))

        data = {"query": '{"age": {"$gte": 30}}'}
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEquals(response.status_code, 200)

        self.assertEqual(1, len(response.data))
        self.assertEqual(45, response.data[0].get('age'))
