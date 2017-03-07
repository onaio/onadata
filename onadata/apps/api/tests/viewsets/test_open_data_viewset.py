import json

from django.test import RequestFactory
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User

from onadata.apps.logger.models import OpenData, Instance
from onadata.apps.api.viewsets.open_data_viewset import (
    OpenDataViewSet, replace_special_characters_with_underscores
)
from onadata.apps.main.tests.test_base import TestBase


class TestOpenDataViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        self.view = OpenDataViewSet.as_view({
            'post': 'create',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'data'
        })

    def test_replace_special_characters_with_underscores(self):
        data = ['john_doe[3]/_visual-studio-code']
        self.assertEqual(
            replace_special_characters_with_underscores(
                data,
            ),
            ['john_doe_3___visual_studio_code']
        )

    def get_open_data_object(self):
        ct = ContentType.objects.get_for_model(self.xform)
        _open_data, created = OpenData.objects.get_or_create(
            object_id=self.xform.id,
            defaults={
                'name': self.xform.id_string,
                'content_type': ct,
                'content_object': self.xform,
            }
        )

        return _open_data

    def test_create_open_data_object_with_valid_fields(self):
        initial_count = OpenData.objects.count()
        request = self.factory.post('/', data={})
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        data = {
            'object_id': self.xform.id,
            'data_type': 'xform',
            'name': self.xform.id_string
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(initial_count + 1, OpenData.objects.count())

    def test_create_open_data_object_with_invalid_fields(self):
        data = {
            'data_type': 'xform',
            'name': self.xform.id_string
        }

        data.update({'object_id': None})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {'object_id': [u'A valid integer is required.']}
        )

        # check for xform with non-existent xform id (object_id)
        data.update({'object_id': 1000})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data.pop('object_id')
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            ['Fields object_id, data_type and name are required.']
        )

    def test_get_data_using_uuid(self):
        self._make_submissions()
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(list(response.data)), 4)

    def test_get_data_using_uuid_and_greater_than_query_param(self):
        self._make_submissions()
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        first_instance = Instance.objects.first()
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid

        request = self.factory.get(
            '/', {'gt_id': first_instance.id}, **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(list(response.data)), 3)

    def test_update_open_data_with_valid_fields_and_data(self):
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        data = {'name': 'updated_name'}

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json"
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)

        _open_data = OpenData.objects.last()
        self.assertEqual(_open_data.name, 'updated_name')

    def test_delete_open_data_object(self):
        inital_count = OpenData.objects.count()
        _open_data = self.get_open_data_object()
        self.assertEqual(OpenData.objects.count(), inital_count + 1)

        request = self.factory.delete('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, uuid=_open_data.uuid)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(OpenData.objects.count(), inital_count)

    def test_column_headers_endpoint(self):
        self.view = OpenDataViewSet.as_view({
            'get': 'schema'
        })

        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            ['table_alias', 'column_headers', 'connection_name'],
            response.data.keys()
        )
        connection_name = u"%s_%s" % (
            self.xform.project_id,
            self.xform.id_string
        )
        self.assertEqual(connection_name, response.data.get('connection_name'))
        self.assertEqual(
            u'transportation_2011_07_25',
            response.data.get('table_alias')
        )

    def test_uuid_endpoint(self):
        self.view = OpenDataViewSet.as_view({
            'get': 'uuid'
        })

        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, "Query params data_type and object_id are required"
        )

        data = {
            'object_id': self.xform.id,
            'data_type': 'non_clazz',
        }
        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        _open_data = self.get_open_data_object()
        data = {
            'object_id': self.xform.id,
            'data_type': 'xform',
        }

        # check authenticated user without permission to the object gets
        # 403 response.
        anonymous_user = User.objects.get(username='AnonymousUser')
        anonymous_user_auth = {
            'HTTP_AUTHORIZATION': 'Token %s' % anonymous_user.auth_token
        }
        request = self.factory.get('/', data=data, **anonymous_user_auth)
        response = self.view(request)
        self.assertEqual(response.status_code, 403)

        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'uuid': _open_data.uuid})

    def test_response_if_open_data_object_is_inactive(self):
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        _open_data.active = False
        _open_data.save()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 404)
