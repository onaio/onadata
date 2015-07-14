import geojson
import os
import requests

from django.utils import timezone
from django.test import RequestFactory
from django_digest.test import DigestAuth

from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.main import tests as main_tests
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.logger_tools import create_instance
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.libs.permissions import ReadOnlyRole
from onadata.libs import permissions as role
from onadata.libs.utils.common_tags import MONGO_STRFTIME
from httmock import urlmatch, HTTMock
from onadata.apps.logger.models.instance import get_attachment_url


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"url": "https://hmh2a.enketo.ona.io"}'
    return response


def _data_list(formid):
    return [{
        u'id': formid,
        u'id_string': u'transportation_2011_07_25',
        u'title': 'transportation_2011_07_25',
        u'description': '',
        u'url': u'http://testserver/api/v1/data/%s' % formid
    }]


def _data_instance(dataid):
    return {
        u'_bamboo_dataset_id': u'',
        u'_attachments': [],
        u'_geolocation': [None, None],
        u'_xform_id_string': u'transportation_2011_07_25',
        u'transport/available_transportation_types_to_referral_facility':
        u'none',
        u'_status': u'submitted_via_web',
        u'_id': dataid
    }


class TestDataViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_data(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())

        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_data_list_with_xform_in_delete_async_queue(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        initial_count = len(response.data)

        self.xform.deleted_at = timezone.now()
        self.xform.save()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(len(response.data), initial_count - 1)

    def test_numeric_types_are_rendered_as_required(self):
        tutorial_folder = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'forms', 'tutorial')
        self._publish_xls_file_and_set_xform(os.path.join(tutorial_folder,
                                                          'tutorial.xls'))

        instance_path = os.path.join(tutorial_folder, 'instances', '1.xml')
        create_instance(self.user.username, open(instance_path), [])

        self.assertEqual(self.xform.instances.count(), 1)
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        # check that ONLY values with numeric and decimal types are converted
        self.assertEqual(response.data[0].get('age'), 35)
        self.assertEqual(response.data[0].get('net_worth'), 100000.00)
        self.assertEqual(response.data[0].get('imei'), u'351746052009472')

    def test_data_pagination(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # no page param no pagination
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get('/', data={"page": "1", "page_size": 2},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get('/', data={"page_size": "3"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        request = self.factory.get(
            '/', data={"page": "1", "page_size": "2"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # invalid page returns a 404
        request = self.factory.get('/', data={"page": "invalid"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        # invalid page size is ignores
        request = self.factory.get('/', data={"page_size": "invalid"},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get(
            '/', data={"page": "invalid", "page-size": "invalid"},
            **self.extra)
        response = view(request, pk=formid)

    def test_data_start_limit_no_records(self):
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # no start, limit params
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get('/', data={"start": "1", "limit": 2},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_data_start_limit(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # no start, limit params
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get('/', data={"start": "1", "limit": 2},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get('/', data={"limit": "3"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        request = self.factory.get(
            '/', data={"start": "1", "limit": "2"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # invalid start is ignored, all data is returned
        request = self.factory.get('/', data={"start": "invalid"},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # invalid limit is ignored, all data is returned
        request = self.factory.get('/', data={"limit": "invalid"},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_anon(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        formid = self.xform.pk
        response = view(request, pk=formid)
        # data not found for anonymous access to private data
        self.assertEqual(response.status_code, 404)

        self.xform.shared = True
        self.xform.save()
        response = view(request, pk=formid)
        # access to a shared form but private data
        self.assertEqual(response.status_code, 404)

        self.xform.shared_data = True
        self.xform.save()
        response = view(request, pk=formid)
        # access to a public data
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)

        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_data_public(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_public_anon_user(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_user_public(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_bad_formid(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        formid = 98918
        self.assertEqual(XForm.objects.filter(pk=formid).count(), 0)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        formid = "INVALID"
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)
        data = {u'detail': u'Invalid form ID: INVALID'}
        self.assertEqual(response.data, data)

    def test_data_bad_dataid(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = 'INVALID'
        data = _data_instance(dataid)
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)

    def test_data_with_query_parameter(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by('pk')[0]
        dataid = instance.pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        query_str = '{"_id": "%s"}' % dataid
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = '{"_submission_time": {"$gte": "%s"}}' % submission_time
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        query_str = '{"_id: "%s"}' % dataid
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'),
                         u"Expecting ':' delimiter: line 1 column 9 (char 8)")

    def test_anon_data_list(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_add_form_tag_propagates_to_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        self._make_submissions()
        xform = XForm.objects.all()[0]
        pk = xform.id
        view = XFormViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })
        data_view = DataViewSet.as_view({
            'get': 'list',
        })
        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.data, [])

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        for i in self.xform.instances.all():
            self.assertIn(u'hello', i.tags.names())

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, pk=pk, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        for i in self.xform.instances.all():
            self.assertNotIn(u'hello', i.tags.names())

    def test_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        self._make_submissions()
        submission_count = self.xform.instances.count()
        pk = self.xform.pk
        i = self.xform.instances.all()[0]
        dataid = i.pk
        data_view = DataViewSet.as_view({
            'get': 'list',
        })
        view = DataViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })

        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), submission_count)

        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        self.assertIn(u'hello', Instance.objects.get(pk=dataid).tags.names())

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.data, [u'hello'])

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), submission_count - 1)

        # remove tag "hello"
        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertNotIn(
            u'hello', Instance.objects.get(pk=dataid).tags.names())

    def test_labels_action_with_params(self):
        self._make_submissions()
        xform = XForm.objects.all()[0]
        pk = xform.id
        dataid = xform.instances.all()[0].id
        view = DataViewSet.as_view({
            'get': 'labels'
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid, label='hello')
        self.assertEqual(response.status_code, 200)

    def test_data_list_filter_by_user(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        bobs_data = _data_list(formid)[0]

        previous_user = self.user
        self._create_user_and_login('alice', 'alice')
        self.assertEqual(self.user.username, 'alice')
        self.assertNotEqual(previous_user, self.user)

        ReadOnlyRole.add(self.user, self.xform)

        # publish alice's form
        self._publish_transportation_form()

        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        formid = self.xform.pk
        alice_data = _data_list(formid)[0]

        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        # should be both bob's and alice's form
        self.assertEqual(sorted(response.data),
                         sorted([bobs_data, alice_data]))

        # apply filter, see only bob's forms
        request = self.factory.get('/', data={'owner': 'bob'}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [bobs_data])

        # apply filter, see only alice's forms
        request = self.factory.get('/', data={'owner': 'alice'}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [alice_data])

        # apply filter, see a non existent user
        request = self.factory.get('/', data={'owner': 'noone'}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_get_enketo_edit_url(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'enketo'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk

        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)
        # add data check
        self.assertEqual(
            response.data,
            {'detail': 'return_url not provided.'})

        request = self.factory.get(
            '/',
            data={'return_url': "http://test.io/test_url"}, **self.extra)

        with HTTMock(enketo_mock):
            response = view(request, pk=formid, dataid=dataid)
            self.assertEqual(
                response.data['url'],
                "https://hmh2a.enketo.ona.io")

    def test_get_form_public_data(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        formid = self.xform.pk
        response = view(request, pk=formid)

        # data not found for anonymous access to private data
        self.assertEqual(response.status_code, 404)
        self.xform.shared_data = True
        self.xform.save()

        # access to a public data as anon
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        # access to a public data as other user
        self._create_user_and_login('alice', 'alice')
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(response.data)[0])

    def test_data_w_attachment(self):
        self._submit_transport_instance_w_attachment()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk

        data = {
            u'_bamboo_dataset_id': u'',
            u'_attachments': [{
                'download_url': get_attachment_url(self.attachment),
                'small_download_url':
                get_attachment_url(self.attachment, 'small'),
                'medium_download_url':
                get_attachment_url(self.attachment, 'medium'),
                u'mimetype': self.attachment.mimetype,
                u'instance': self.attachment.instance.pk,
                u'filename': self.attachment.media_file.name,
                u'id': self.attachment.pk,
                u'xform': self.xform.id}
            ],
            u'_geolocation': [None, None],
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_status': u'submitted_via_web',
            u'_id': dataid
        }
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_delete_submission(self):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk
        view = DataViewSet.as_view({
            'delete': 'destroy',
            'get': 'list'
        })

        # 4 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)

        self._create_user_and_login(username='alice', password='alice')
        # Managers can delete
        role.ManagerRole.add(self.user, self.xform)
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.delete('/', **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None)\
            .order_by('id')[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 2)

    def test_geojson_format(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        view = DataViewSet.as_view({'get': 'retrieve'})
        data_get = {
            "fields": 'today'
        }
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)

        test_geo = {
            'type': 'Feature',
            'geometry': {
                u'type': u'GeometryCollection',
                u'geometries': [{
                    u'type': u'Point',
                    u'coordinates': [
                        36.787219,
                        -1.294197
                    ]
                }
                ]
            },
            'properties': {
                'id': dataid,
                'xform': self.xform.pk,
                'today': '2015-01-15'
            }
        }

        self.assertEqual(response.data, test_geo)

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')
        instances = self.xform.instances.all()
        data = {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[0].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[1].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[2].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[3].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                }
            ]
            }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_geojson_geofield(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data_get = {
            "geo_field": 'location',
            "fields": 'today'
        }

        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)
        test_loc = geojson.Feature(
            geometry=geojson.GeometryCollection([
                geojson.Point((36.787219, -1.294197))]),
            properties={
                'xform': self.xform.pk,
                'id': dataid,
                u'today': '2015-01-15'
            }
        )
        if 'id' in test_loc:
            test_loc.pop('id')

        self.assertEqual(response.data, test_loc)

        view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')

        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data['type'], 'FeatureCollection')
        self.assertEquals(len(response.data['features']), 4)
        self.assertEquals(response.data['features'][0]['type'], 'Feature')
        self.assertEquals(
            response.data['features'][0]['geometry']['geometries'][0]['type'],
            'Point'
        )

    def test_geojson_linestring(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data_get = {
            "geo_field": 'path',
            "fields": 'today,path'
        }

        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)

        self.assertEquals(response.data['type'], 'Feature')
        self.assertEquals(len(response.data['geometry']['coordinates']), 5)
        self.assertIn('path', response.data['properties'])
        self.assertEquals(response.data['geometry']['type'], 'LineString')

        view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')

        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data['type'], 'FeatureCollection')
        self.assertEquals(len(response.data['features']), 4)
        self.assertEquals(response.data['features'][0]['type'], 'Feature')
        self.assertEquals(response.data['features'][0]['geometry']['type'],
                          'LineString')

    def test_geojson_polygon(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data_get = {
            "geo_field": 'shape',
            "fields": 'today,shape'
        }

        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)

        self.assertEquals(response.data['type'], 'Feature')
        self.assertEquals(len(response.data['geometry']['coordinates'][0]), 6)
        self.assertIn('shape', response.data['properties'])
        self.assertEquals(response.data['geometry']['type'], 'Polygon')

        view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')

        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data['type'], 'FeatureCollection')
        self.assertEquals(len(response.data['features']), 4)
        self.assertEquals(response.data['features'][0]['type'], 'Feature')
        self.assertEquals(response.data['features'][0]['geometry']['type'],
                          'Polygon')

    def test_data_in_public_project(self):
        self._make_submissions()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        self.assertEquals(response.status_code, 200)
        self.assertEqual(len(response.data), 4)
        # get project id
        projectid = self.xform.project.pk

        view = ProjectViewSet.as_view({
            'put': 'update'
        })

        data = {'shared': True,
                'name': 'test project',
                'owner': 'http://testserver/api/v1/users/%s'
                % self.user.username}
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 200)

        # anonymous user
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_diff_version(self):
        self._make_submissions()

        # update the form version
        self.xform.version = "212121211"
        self.xform.save()

        # make more submission after form update
        surveys = ['transport_2011-07-25_19-05-36-edited']
        main_directory = os.path.dirname(main_tests.__file__)
        paths = [os.path.join(main_directory, 'fixtures', 'transportation',
                              'instances_w_uuid', s, s + '.xml')
                 for s in surveys]

        auth = DigestAuth('bob', 'bob')
        for path in paths:
            self._make_submission(path, None, None, auth=auth)

        data_view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', **self.extra)

        response = data_view(request, pk=self.xform.pk)

        self.assertEquals(len(response.data), 5)

        query_str = '{"_version": "2014111"}'
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = data_view(request, pk=self.xform.pk)

        self.assertEquals(len(response.data), 4)

        query_str = '{"_version": "212121211"}'
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = data_view(request, pk=self.xform.pk)

        self.assertEquals(len(response.data), 1)

    def test_etag_on_response(self):
        self._make_submissions()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)
        self.assertEqual(response.get('Cache-Control'), 'max-age=60')

        self.assertIsNotNone(response.get('ETag'))
        etag_hash = response.get('ETag')

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)

        self.assertEquals(etag_hash, response.get('ETag'))

        # delete one submission
        inst = Instance.objects.filter(xform=self.xform)
        inst[0].delete()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)

        self.assertNotEquals(etag_hash, response.get('ETag'))


class TestOSM(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._login_user_and_profile()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_data_retrieve_instance_osm_format(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename)
            for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        files = [open(path) for path in paths]
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission(submission_path, media_file=files)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        formid = self.xform.pk
        dataid = self.xform.instances.latest('date_created').pk
        request = self.factory.get('/', **self.extra)

        # look at the data/[pk]/[dataid].osm endpoint
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid, format='osm')
        self.assertEqual(response.status_code, 200)
        with open(combined_osm_path) as f:
            osm = f.read()
            response.render()
            self.assertMultiLineEqual(response.content, osm)

            # look at the data/[pk].osm endpoint
            view = DataViewSet.as_view({'get': 'list'})
            response = view(request, pk=formid, format='osm')
            self.assertEqual(response.status_code, 200)
            response.render()
            self.assertMultiLineEqual(response.content, osm)
