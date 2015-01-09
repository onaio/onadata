import requests

from django.test import RequestFactory

from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm
from onadata.libs.permissions import ReadOnlyRole
from onadata.libs import permissions as role
from httmock import urlmatch, HTTMock


@urlmatch(netloc=r'(.*\.)?enketo\.formhub\.org$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"url": "https://hmh2a.enketo.formhub.org"}'
    return response


def _data_list(formid):
    return [{
        u'id': formid,
        u'id_string': u'transportation_2011_07_25',
        u'title': 'transportation_2011_07_25',
        u'description': 'transportation_2011_07_25',
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
        self.assertNotEqual(response.get('Last-Modified'), None)
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
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_data_with_limit_operator(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        request = self.factory.get('/', data={"start": "2"}, **self.extra)
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

        request = self.factory.get('/', data={"start": "start"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get('/', data={"limit": "limit"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get(
            '/', data={"start": "start", "limit": "start"}, **self.extra)
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
        self.assertEqual(response.get('Last-Modified'), None)
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
        self.assertEqual(response.get('Last-Modified'), None)

    def test_data_with_query_parameter(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        dataid = self.xform.instances.all()[0].pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)
        query_str = '{"_id": "%s"}' % dataid
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

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
        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.data, [])
        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        for i in self.xform.instances.all():
            self.assertIn(u'hello', i.tags.names())
        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, pk=pk, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        for i in self.xform.instances.all():
            self.assertNotIn(u'hello', i.tags.names())

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
        self.assertEqual(response.get('Last-Modified'), None)
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
                "https://hmh2a.enketo.formhub.org")

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
            u'_attachments': [{u'download_url': self.attachment.media_file.url,
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
        before_count = self.xform.instances.all().count()
        view = DataViewSet.as_view({'delete': 'destroy'})
        request = self.factory.delete('/', **self.extra)
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk

        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)
        count = self.xform.instances.all().count()
        self.assertEquals(before_count - 1, count)

        self._create_user_and_login(username='alice', password='alice')
        # Managers can delete
        role.ManagerRole.add(self.user, self.xform)
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.delete('/', **self.extra)
        dataid = self.xform.instances.all().order_by('id')[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)
        count = self.xform.instances.all().count()
        self.assertEquals(before_count - 2, count)
