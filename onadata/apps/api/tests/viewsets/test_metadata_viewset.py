import os
from builtins import open

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.permissions import (DataEntryRole, DataEntryOnlyRole,
                                      EditorRole, EditorMinorRole)
from onadata.libs.serializers.metadata_serializer import UNIQUE_TOGETHER_ERROR
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils.common_tags import XFORM_META_PERMS


class TestMetaDataViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestMetaDataViewSet, self).setUp()
        self.view = MetaDataViewSet.as_view({
            'delete': 'destroy',
            'get': 'retrieve',
            'post': 'create'
        })
        self._publish_xls_form_to_project()
        self.data_value = "screenshot.png"
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation"
        )
        self.path = os.path.join(self.fixture_dir, self.data_value)

        ContentType.objects.get_or_create(app_label="logger", model="project")
        ContentType.objects.get_or_create(app_label="logger", model="instance")

    def _add_project_metadata(self, project, data_type, data_value, path=None):
        data = {
            'data_type': data_type,
            'data_value': data_value,
            'project': project.id
        }

        if path and data_value:
            with open(path, 'rb') as media_file:
                data.update({
                    'data_file': media_file,
                })
                return self._post_metadata(data)
        else:
            return self._post_metadata(data)

    def _add_instance_metadata(self,
                               data_type,
                               data_value,
                               path=None):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures",
            "tutorial", "tutorial.xls")

        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        xml_submission_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures",
            "tutorial", "instances", "tutorial_2012-06-27_11-27-53.xml")

        self._make_submission(xml_submission_file_path,
                              username=self.user.username)
        self.xform.refresh_from_db()
        self.instance = self.xform.instances.first()

        data = {
            'data_type': data_type,
            'data_value': data_value,
            'instance': self.instance.id
        }

        if path and data_value:
            with open(path, 'rb') as media_file:
                data.update({
                    'data_file': media_file,
                })
                self._post_metadata(data)
        else:
            self._post_metadata(data)

    def test_add_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)

    def test_parse_error_is_raised(self):
        """Parse error is raised when duplicate media is uploaded"""
        data_type = "supporting_doc"

        self._add_form_metadata(self.xform, data_type,
                                self.data_value, self.path)
        # Duplicate upload
        response = self._add_form_metadata(self.xform, data_type,
                                           self.data_value, self.path, False)
        self.assertEquals(response.status_code, 400)
        self.assertIn(UNIQUE_TOGETHER_ERROR, response.data)

    def test_forms_endpoint_with_metadata(self):
        date_modified = self.xform.date_modified
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            self.xform.refresh_from_db()
            self.assertNotEqual(date_modified, self.xform.date_modified)

        # /forms
        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = XFormSerializer(self.xform, context={'request': request}).data
        self.assertEqual(response.data, data)

        # /projects/[pk]/forms
        view = ProjectViewSet.as_view({
            'get': 'forms'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [data])

    def test_get_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            request = self.factory.get('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertNotEqual(response.get('Cache-Control'), None)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.metadata_data)
            ext = self.data_value[self.data_value.rindex('.') + 1:]
            request = self.factory.get('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk, format=ext)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')

    def test_get_metadata(self):
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "instances", "transport_2011-07-25_19-05-49"
        )
        self.data_value = '1335783522563.jpg'
        self.path = os.path.join(self.fixture_dir, self.data_value)

        self._add_form_metadata(
            self.xform, "media", self.data_value, self.path)
        data = {
            'id': self.metadata.pk,
            'xform': self.xform.pk,
            'data_value': u'1335783522563.jpg',
            'data_type': u'media',
            'data_file': u'http://localhost:8000/media/%s/formid-media/'
            '1335783522563.jpg' % self.user.username,
            'data_file_type': u'image/jpeg',
            'media_url': u'http://localhost:8000/media/%s/formid-media/'
            '1335783522563.jpg' % self.user.username,
            'file_hash': u'md5:2ca0d22073a9b6b4ebe51368b08da60c',
            'url': 'http://testserver/api/v1/metadata/%s' % self.metadata.pk,
            'date_created': self.metadata.date_created
        }
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.metadata.pk)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(dict(response.data), data)

    def test_add_mapbox_layer(self):
        data_type = 'mapbox_layer'
        data_value = 'test_mapbox_layer||http://0.0.0.0:8080||attribution'
        self._add_form_metadata(self.xform, data_type, data_value)

    def test_delete_metadata(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            count = MetaData.objects.count()
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            request = self.factory.delete('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(count, MetaData.objects.count())

    def test_windows_csv_file_upload_to_metadata(self):
        data_value = 'transportation.csv'
        path = os.path.join(self.fixture_dir, data_value)
        with open(path) as f:
            f = InMemoryUploadedFile(
                f, 'media', data_value, 'application/octet-stream', 2625, None)
            data = {
                'data_value': data_value,
                'data_file': f,
                'data_type': 'media',
                'xform': self.xform.pk
            }
            self._post_metadata(data)
            self.assertEqual(self.metadata.data_file_type, 'text/csv')

    def test_add_media_url(self):
        data_type = 'media'

        # test invalid URL
        data_value = 'some thing random here'
        response = self._add_form_metadata(
            self.xform, data_type, data_value, test=False)
        expected_exception = {
            'data_value': [u"Invalid url 'some thing random here'."]
        }
        self.assertEqual(response.data, expected_exception)

        # test valid URL
        data_value = 'https://devtrac.ona.io/fieldtrips.csv'
        self._add_form_metadata(self.xform, data_type, data_value)
        request = self.factory.get('/', **self.extra)
        ext = self.data_value[self.data_value.rindex('.') + 1:]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], data_value)

    def test_add_media_xform_link(self):
        data_type = 'media'

        # test missing parameters
        data_value = 'xform {}'.format(self.xform.pk)
        response = self._add_form_metadata(
            self.xform, data_type, data_value, test=False)
        expected_exception = {
            'data_value': [
                u"Expecting 'xform [xform id] [media name]' or "
                "'dataview [dataview id] [media name]' or a valid URL."]
        }
        self.assertEqual(response.data, expected_exception)

        data_value = 'xform {} transportation'.format(self.xform.pk)
        self._add_form_metadata(self.xform, data_type, data_value)
        self.assertIsNotNone(self.metadata_data['media_url'])

        request = self.factory.get('/', **self.extra)
        ext = self.data_value[self.data_value.rindex('.') + 1:]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'],
                         'attachment; filename=transportation.csv')

    def test_add_media_dataview_link(self):
        self._create_dataview()
        data_type = 'media'
        data_value = 'dataview {} transportation'.format(self.data_view.pk)
        self._add_form_metadata(self.xform, data_type, data_value)
        self.assertIsNotNone(self.metadata_data['media_url'])

        request = self.factory.get('/', **self.extra)
        ext = self.data_value[self.data_value.rindex('.') + 1:]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'],
                         'attachment; filename=transportation.csv')

    def test_invalid_post(self):
        response = self._post_metadata({}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({
            'data_type': 'supporting_doc'}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({
            'data_type': 'supporting_doc',
            'xform': self.xform.pk
        }, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({
            'data_type': 'supporting_doc',
            'data_value': 'supporting.doc'
        }, False)
        self.assertEqual(response.status_code, 400)

    def _add_test_metadata(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)

    def test_list_metadata(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

    def test_list_metadata_for_specific_form(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({'get': 'list'})
        data = {'xform': self.xform.pk}
        request = self.factory.get('/', data)
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

        data['xform'] = 1234509909
        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data['xform'] = "INVALID"
        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

    def test_project_metadata_has_project_field(self):
        self._add_project_metadata(
            self.project, 'supporting_doc', self.data_value, self.path)

        # Test json of project metadata
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.metadata_data['id'])

        self.assertEqual(response.status_code, 200)

        data = dict(response.data)

        self.assertIsNotNone(data['media_url'])
        self.assertEqual(data['project'], self.metadata.object_id)

    def test_instance_metadata_has_instance_field(self):
        self._add_instance_metadata(
            'supporting_doc', self.data_value, self.path)

        # Test json of project metadata
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.metadata_data['id'])

        self.assertEqual(response.status_code, 200)

        data = dict(response.data)

        self.assertIsNotNone(data['media_url'])
        self.assertEqual(data['instance'], self.metadata.object_id)

    def test_should_return_both_xform_and_project_metadata(self):
        # delete all existing metadata
        MetaData.objects.all().delete()
        expected_metadata_count = 2

        project_response = self._add_project_metadata(
            self.project, 'media', "check.png", self.path)
        self.assertTrue("image/png" in project_response.data['data_file_type'])

        form_response = self._add_form_metadata(
            self.xform, 'supporting_doc', "bla.png", self.path)
        self.assertTrue("image/png" in form_response.data['data_file_type'])

        view = MetaDataViewSet.as_view({'get': 'list'})
        request = self.factory.get("/", **self.extra)
        response = view(request)

        self.assertEquals(MetaData.objects.count(), expected_metadata_count)

        for record in response.data:
            if record.get("xform"):
                self.assertEquals(record.get('xform'), self.xform.id)
                self.assertIsNone(record.get('project'))
            else:
                self.assertEquals(record.get('project'), self.project.id)
                self.assertIsNone(record.get('xform'))

    def test_should_only_return_xform_metadata(self):
        # delete all existing metadata
        MetaData.objects.all().delete()

        self._add_project_metadata(
            self.project, 'media', "check.png", self.path)

        self._add_form_metadata(
            self.xform, 'supporting_doc', "bla.png", self.path)

        view = MetaDataViewSet.as_view({'get': 'list'})
        query_data = {"xform": self.xform.id}
        request = self.factory.get("/", data=query_data, **self.extra)
        response = view(request)

        self.assertEqual(len(response.data), 1)
        self.assertIn("xform", response.data[0])
        self.assertNotIn("project", response.data[0])

    def _create_metadata_object(self):
        view = MetaDataViewSet.as_view({'post': 'create'})
        with open(self.path, 'rb') as media_file:
            data = {
                'data_type': 'media',
                'data_value': 'check.png',
                'data_file': media_file,
                'project': self.project.id
            }
            request = self.factory.post('/', data, **self.extra)
            response = view(request)

            return response

    def test_integrity_error_is_handled(self):
        count = MetaData.objects.count()

        response = self._create_metadata_object()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(count + 1, MetaData.objects.count())

        response = self._create_metadata_object()
        self.assertEqual(response.status_code, 400)

    def test_invalid_form_metadata(self):
        view = MetaDataViewSet.as_view({'post': 'create'})
        with open(self.path, 'rb') as media_file:
            data = {
                'data_type': "media",
                'data_value': self.data_value,
                'xform': 999912,
                'data_file': media_file,
            }

            request = self.factory.post('/', data, **self.extra)
            response = view(request)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data,
                             {'xform': ['XForm does not exist']})

    def test_xform_meta_permission(self):
        view = MetaDataViewSet.as_view({'post': 'create'})

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor-minor|dataentry',
            'xform': self.xform.pk
        }
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        meta = MetaData.xform_meta_permission(self.xform)
        self.assertEqual(meta.data_value, response.data.get('data_value'))

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor-minors|invalid_role',
            'xform': self.xform.pk
        }
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 400)
        error = u"Format 'role'|'role' or Invalid role"
        self.assertEqual(response.data, {'non_field_errors': [error]})

    def test_role_update_xform_meta_perms(self):
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        EditorRole.add(alice_profile.user, self.xform)

        view = MetaDataViewSet.as_view({
            'post': 'create',
            'put': 'update'
        })

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor-minor|dataentry',
            'xform': self.xform.pk
        }
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        self.assertFalse(
            EditorRole.user_has_role(alice_profile.user, self.xform))

        self.assertTrue(
            EditorMinorRole.user_has_role(alice_profile.user, self.xform))

        meta = MetaData.xform_meta_permission(self.xform)

        DataEntryRole.add(alice_profile.user, self.xform)

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor|dataentry-only',
            'xform': self.xform.pk
        }
        request = self.factory.put('/', data, **self.extra)
        response = view(request, pk=meta.pk)

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            DataEntryRole.user_has_role(alice_profile.user, self.xform))

        self.assertTrue(
            DataEntryOnlyRole.user_has_role(alice_profile.user, self.xform))

    def test_xform_meta_perms_duplicates(self):
        view = MetaDataViewSet.as_view({
            'post': 'create',
            'put': 'update'
        })

        ct = ContentType.objects.get_for_model(self.xform)

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor-minor|dataentry',
            'xform': self.xform.pk
        }
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        count = MetaData.objects.filter(data_type=XFORM_META_PERMS,
                                        object_id=self.xform.pk,
                                        content_type=ct.pk).count()

        self.assertEqual(1, count)

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor-minor|dataentry-only',
            'xform': self.xform.pk
        }
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        count = MetaData.objects.filter(data_type=XFORM_META_PERMS,
                                        object_id=self.xform.pk,
                                        content_type=ct.pk).count()

        self.assertEqual(1, count)

        metadata = MetaData.xform_meta_permission(self.xform)
        self.assertEqual(metadata.data_value, "editor-minor|dataentry-only")

    def test_unique_submission_review_metadata(self):
        """Don't create duplicate submission_review for a form"""
        data_type = "submission_review"
        data_value = True

        response = self._add_form_metadata(self.xform, data_type, data_value)
        # Duplicate with different Data Value

        view = MetaDataViewSet.as_view({'post': 'create'})
        data = {
            'xform': response.data['xform'],
            'data_type': data_type,
            'data_value': False,
        }
        request = self.factory.post('/', data, **self.extra)
        d_response = view(request)

        self.assertEquals(d_response.status_code, 400)
        self.assertIn(UNIQUE_TOGETHER_ERROR, d_response.data)
