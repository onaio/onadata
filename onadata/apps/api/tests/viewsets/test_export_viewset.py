import os

from django.test import RequestFactory

from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.main.tests.test_base import TestBase


class TestDataViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def _filename_from_disposition(self, content_disposition):
        filename_pos = content_disposition.index('filename=')
        self.assertTrue(filename_pos != -1)
        return content_disposition[filename_pos + len('filename='):]

    def test_form_list(self):
        view = ExportViewSet.as_view({
            'get': 'list',
        })
        data = {
            'owner': 'http://testserver/api/v1/users/bob',
            'public': False,
            'public_data': False,
            'description': u'',
            'downloadable': True,
            'is_crowd_form': False,
            'allows_sms': False,
            'encrypted': False,
            'sms_id_string': u'transportation_2011_07_25',
            'id_string': u'transportation_2011_07_25',
            'title': u'transportation_2011_07_25',
            'bamboo_dataset': u''
        }
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(data, response.data[0])

    def test_form_get(self):
        self._make_submissions()
        view = ExportViewSet.as_view({
            'get': 'retrieve'
        })
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'detail': 'Expected URL keyword argument `owner`.'})

        # csv
        request = self.factory.get('/', **self.extra)
        response = view(request, owner='bob', pk=formid, format='csv')
        self.assertEqual(response.status_code, 200)
        headers = dict(response.items())
        content_disposition = headers['Content-Disposition']
        filename = self._filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(headers['Content-Type'], 'application/csv')
        self.assertEqual(ext, '.csv')
