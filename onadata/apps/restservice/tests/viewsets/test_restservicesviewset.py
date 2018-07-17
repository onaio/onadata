from django.test.utils import override_settings
from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.viewsets.restservices_viewset import \
    RestServicesViewSet


class TestRestServicesViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestRestServicesViewSet, self).setUp()
        self.view = RestServicesViewSet.as_view({
            'delete': 'destroy',
            'get': 'retrieve',
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update'
        })
        self._publish_xls_form_to_project()

    def test_create(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "generic_json",
            "service_url": "https://textit.io",
            "xform": self.xform.pk
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count + 1, RestService.objects.all().count())

    def test_textit_service_missing_params(self):
        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)

    def _create_textit_service(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count + 1, RestService.objects.all().count())

        meta = MetaData.objects.filter(object_id=self.xform.id,
                                       data_type='textit')
        self.assertEquals(len(meta), 1)
        rs = RestService.objects.last()

        expected_dict = {
            'name': u'textit',
            'contacts': u'ksadaskjdajsda',
            'auth_token': u'sadsdfhsdf',
            'flow_uuid': u'sdfskhfskdjhfs',
            'service_url': u'https://textit.io',
            'id': rs.pk,
            'xform': self.xform.pk,
            'active': True,
            'inactive_reason': ''
        }
        response.data.pop('date_modified')
        response.data.pop('date_created')

        self.assertEqual(response.data, expected_dict)

        return response.data

    def test_create_textit_service(self):
        self._create_textit_service()

    def test_retrieve_textit_services(self):
        response_data = self._create_textit_service()

        _id = response_data.get('id')

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=_id)
        expected_dict = {
            'name': u'textit',
            'contacts': u'ksadaskjdajsda',
            'auth_token': u'sadsdfhsdf',
            'flow_uuid': u'sdfskhfskdjhfs',
            'service_url': u'https://textit.io',
            'id': _id,
            'xform': self.xform.pk,
            'active': True,
            'inactive_reason': ''
        }
        response.data.pop('date_modified')
        response.data.pop('date_created')

        self.assertEqual(response.data, expected_dict)

    def test_delete_textit_service(self):
        rest = self._create_textit_service()
        count = RestService.objects.all().count()
        meta_count = MetaData.objects.filter(object_id=self.xform.id,
                                             data_type='textit').count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=rest['id'])

        self.assertEquals(response.status_code, 204)
        self.assertEquals(count - 1, RestService.objects.all().count())
        a_meta_count = MetaData.objects.filter(object_id=self.xform.id,
                                               data_type='textit').count()
        self.assertEqual(meta_count - 1, a_meta_count)

    def test_update(self):
        rest = RestService(name="testservice",
                           service_url="http://serviec.io",
                           xform=self.xform)
        rest.save()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }

        request = self.factory.put('/', data=post_data, **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], "textit")

    def test_update_with_errors(self):
        rest = self._create_textit_service()

        data_value = "{}|{}".format("test", "test2")
        MetaData.textit(self.xform, data_value)

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=rest.get('id'))

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data,
                          [u"Error occurred when loading textit service."
                           u"Resolve by updating auth_token, flow_uuid and "
                           u"contacts fields"])

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }

        request = self.factory.put('/', data=post_data, **self.extra)
        response = self.view(request, pk=rest.get('id'))

        self.assertEquals(response.status_code, 200)

    def test_delete(self):
        rest = RestService(name="testservice",
                           service_url="http://serviec.io",
                           xform=self.xform)
        rest.save()

        count = RestService.objects.all().count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEquals(response.status_code, 204)
        self.assertEquals(count - 1, RestService.objects.all().count())

    def test_retrieve(self):
        rest = RestService(name="testservice",
                           service_url="http://serviec.io",
                           xform=self.xform)
        rest.save()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=rest.pk)

        data = {
            'id': rest.pk,
            'xform': self.xform.pk,
            'name': u'testservice',
            'service_url': u'http://serviec.io',
            'active': True,
            'inactive_reason': ''
        }
        response.data.pop('date_modified')
        response.data.pop('date_created')
        self.assertEquals(response.status_code, 200)

        self.assertEquals(response.data, data)

    def test_duplicate_rest_service(self):
        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('requests.post')
    def test_textit_flow(self, mock_http):
        rest = RestService(name="textit",
                           service_url="https://server.io",
                           xform=self.xform)
        rest.save()

        MetaData.textit(self.xform,
                        data_value='{}|{}|{}'.format("sadsdfhsdf",
                                                     "sdfskhfskdjhfs",
                                                     "ksadaskjdajsda"))

        self.assertFalse(mock_http.called)
        self._make_submissions()

        self.assertTrue(mock_http.called)
        self.assertEquals(mock_http.call_count, 4)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('requests.post')
    def test_textit_flow_without_parsed_instances(self, mock_http):
        rest = RestService(name="textit",
                           service_url="https://server.io",
                           xform=self.xform)
        rest.save()

        MetaData.textit(self.xform,
                        data_value='{}|{}|{}'.format("sadsdfhsdf",
                                                     "sdfskhfskdjhfs",
                                                     "ksadaskjdajsda"))
        self.assertFalse(mock_http.called)
        self._make_submissions()
        self.assertTrue(mock_http.called)

    def test_create_rest_service_invalid_form_id(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": "invalid",
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEqual(response.data, {'xform': [u'Invalid form id']})
        self.assertEquals(count, RestService.objects.all().count())
