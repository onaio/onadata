import os

from past.builtins import basestring

from django.utils import timezone

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.attachment_viewset import AttachmentViewSet
from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import get_attachment_url


def attachment_url(attachment, suffix=None):
    path = get_attachment_url(attachment, suffix)

    return u'http://testserver{}'.format(path)


class TestAttachmentViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestAttachmentViewSet, self).setUp()
        self.retrieve_view = AttachmentViewSet.as_view({
            'get': 'retrieve'
        })
        self.list_view = AttachmentViewSet.as_view({
            'get': 'list'
        })

        self._publish_xls_form_to_project()

    def test_retrieve_view(self):
        self._submit_transport_instance_w_attachment()

        pk = self.attachment.pk

        data = {
            'url': 'http://testserver/api/v1/media/%s' % pk,
            'field_xpath': None,
            'download_url': attachment_url(self.attachment),
            'small_download_url': attachment_url(self.attachment, 'small'),
            'medium_download_url': attachment_url(self.attachment, 'medium'),
            'id': pk,
            'xform': self.xform.pk,
            'instance': self.attachment.instance.pk,
            'mimetype': self.attachment.mimetype,
            'filename': self.attachment.media_file.name
        }
        request = self.factory.get('/', **self.extra)
        response = self.retrieve_view(request, pk=pk)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, dict))
        self.assertEqual(response.data, data)

        # file download
        filename = data['filename']
        ext = filename[filename.rindex('.') + 1:]
        request = self.factory.get('/', **self.extra)
        response = self.retrieve_view(request, pk=pk, format=ext)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'image/jpeg')

        self.attachment.instance.xform.deleted_at = timezone.now()
        self.attachment.instance.xform.save()
        request = self.factory.get('/', **self.extra)
        response = self.retrieve_view(request, pk=pk)
        self.assertEqual(response.status_code, 404)

    def test_attachment_pagination(self):
        """
        Test attachments endpoint pagination support.
        """
        self._submit_transport_instance_w_attachment()
        self.assertEqual(self.response.status_code, 201)
        filename = "1335783522564.JPG"
        path = os.path.join(self.main_directory, 'fixtures', 'transportation',
                            'instances', self.surveys[0], filename)
        media_file = django_file(path, 'image2', 'image/jpeg')
        Attachment.objects.create(
            instance=self.xform.instances.first(),
            mimetype='image/jpeg',
            extension='JPG',
            name=filename,
            media_file=media_file)

        # not using pagination params
        request = self.factory.get('/', **self.extra)
        response = self.list_view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 2)

        # valid page and page_size
        request = self.factory.get(
            '/', data={"page": 1, "page_size": 1}, **self.extra)
        response = self.list_view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 1)

        # invalid page type
        request = self.factory.get('/', data={"page": "invalid"}, **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 404)

        # invalid page size type
        request = self.factory.get('/', data={"page_size": "invalid"},
                                   **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 2)

        # invalid page and page_size types
        request = self.factory.get(
            '/', data={"page": "invalid", "page_size": "invalid"},
            **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 404)

        # invalid page size
        request = self.factory.get(
            '/', data={"page": 4, "page_size": 1}, **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_and_list_views_with_anonymous_user(self):
        """Retrieve metadata of a public form"""
        # anon user private form access not allowed
        self._submit_transport_instance_w_attachment()
        pk = self.attachment.pk
        xform_id = self.attachment.instance.xform.id

        request = self.factory.get('/')
        response = self.retrieve_view(request, pk=pk)
        self.assertEqual(response.status_code, 404)

        request = self.factory.get('/')
        response = self.list_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        request = self.factory.get('/', data={"xform": xform_id})
        response = self.list_view(request)
        self.assertEqual(response.status_code, 404)

        xform = self.attachment.instance.xform
        xform.shared_data = True
        xform.save()

        request = self.factory.get('/')
        response = self.retrieve_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)

        request = self.factory.get('/')
        response = self.list_view(request)
        self.assertEqual(response.status_code, 200)

        request = self.factory.get('/', data={"xform": xform_id})
        response = self.list_view(request)
        self.assertEqual(response.status_code, 200)

    def test_list_view(self):
        self._submit_transport_instance_w_attachment()

        request = self.factory.get('/', **self.extra)
        response = self.list_view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 1)

        # test when the submission is soft deleted
        self.attachment.instance.deleted_at = timezone.now()
        self.attachment.instance.save()

        request = self.factory.get('/', **self.extra)
        response = self.list_view(request)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 0)

    def test_data_list_with_xform_in_delete_async(self):
        self._submit_transport_instance_w_attachment()

        request = self.factory.get('/', **self.extra)
        response = self.list_view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        initial_count = len(response.data)

        self.xform.deleted_at = timezone.now()
        self.xform.save()
        request = self.factory.get('/', **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), initial_count - 1)

    def test_list_view_filter_by_xform(self):
        self._submit_transport_instance_w_attachment()

        data = {
            'xform': self.xform.pk
        }
        request = self.factory.get('/', data, **self.extra)
        response = self.list_view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))

        data['xform'] = 10000000
        request = self.factory.get('/', data, **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 404)

        data['xform'] = 'lol'
        request = self.factory.get('/', data, **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)

    def test_list_view_filter_by_instance(self):
        self._submit_transport_instance_w_attachment()

        data = {
            'instance': self.attachment.instance.pk
        }
        request = self.factory.get('/', data, **self.extra)
        response = self.list_view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))

        data['instance'] = 10000000
        request = self.factory.get('/', data, **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 404)

        data['instance'] = 'lol'
        request = self.factory.get('/', data, **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)

    def test_direct_image_link(self):
        self._submit_transport_instance_w_attachment()

        data = {
            'filename': self.attachment.media_file.name
        }
        request = self.factory.get('/', data, **self.extra)
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, basestring))
        self.assertEqual(response.data, attachment_url(self.attachment))

        data['filename'] = 10000000
        request = self.factory.get('/', data, **self.extra)
        response = self.retrieve_view(request, pk=self.attachment.instance.pk)
        self.assertEqual(response.status_code, 404)

        data['filename'] = 'lol'
        request = self.factory.get('/', data, **self.extra)
        response = self.retrieve_view(request, pk=self.attachment.instance.pk)
        self.assertEqual(response.status_code, 404)

    def test_direct_image_link_uppercase(self):
        self._submit_transport_instance_w_attachment()
        filename = "1335783522564.JPG"
        path = os.path.join(self.main_directory, 'fixtures', 'transportation',
                            'instances', self.surveys[0], filename)
        self.attachment.media_file = django_file(path, 'image2', 'image/jpeg')
        self.attachment.name = filename
        self.attachment.save()

        filename = self.attachment.media_file.name
        file_base, file_extension = os.path.splitext(filename)
        data = {
            'filename': file_base + file_extension.upper()
        }
        request = self.factory.get('/', data, **self.extra)
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, basestring))
        self.assertEqual(response.data, attachment_url(self.attachment))
