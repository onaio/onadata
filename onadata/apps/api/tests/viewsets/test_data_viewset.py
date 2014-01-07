from django.test import RequestFactory

from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.note_viewset import NoteViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_logger.models import XForm


class TestDataViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_data(self):
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = {
            u'transportation_2011_07_25':
            'http://testserver/api/v1/data/bob/%s' % formid
        }
        self.assertDictEqual(response.data, data)
        response = view(request, owner='bob', formid=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.surveys.count())
        dataid = self.xform.surveys.all().order_by('id')[0].pk

        data = {
            u'_bamboo_dataset_id': u'',
            u'_attachments': [],
            u'_geolocation': [None, None],
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_status': u'submitted_via_web',
            u'_id': dataid
        }
        self.assertDictContainsSubset(data, sorted(response.data)[0])
        response = view(request, owner='bob', formid=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_data_with_query_parameter(self):
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        dataid = self.xform.surveys.all()[0].pk
        response = view(request, owner='bob', formid=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)
        query_str = '{"_id": "%s"}' % dataid
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, owner='bob', formid=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_anon_form_list(self):
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 401)

    def test_add_form_tag_propagates_to_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        xform = XForm.objects.all()[0]
        pk = _id = xform.id
        view = XFormViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })
        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, owner='bob', pk=pk, formid=_id)
        self.assertEqual(response.data, [])
        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, owner='bob', pk=pk, formid=_id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        for i in self.xform.surveys.all():
            self.assertIn(u'hello', i.tags.names())
        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, owner='bob', pk=pk, formid=_id, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        for i in self.xform.surveys.all():
            self.assertNotIn(u'hello', i.tags.names())

    def test_add_notes_to_data_point(self):
        # add a note to a specific data point
        view = NoteViewSet.as_view({
            'get': 'retrieve',
            'post': 'create',
        })
        note = {'note': u"Road Warrior"}
        dataid = self.xform.surveys.all()[0].pk
        note['instance'] = dataid
        request = self.factory.post('/', data=note, **self.extra)
        self.assertTrue(self.xform.surveys.count())
        response = view(request)
        self.assertEqual(response.status_code, 201)
        pk = response.data['id']
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(note, response.data)
        view = NoteViewSet.as_view({
            'get': 'list',
            'delete': 'destroy'
        })
        user = self._create_user('deno', 'deno')
        extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % user.auth_token}
        request = self.factory.get('/', **extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data, [])
        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.status_code, 204)
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data, [])
