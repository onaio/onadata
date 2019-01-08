import os

from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet
from onadata.apps.logger.models import Attachment


def attachment_url(attachment, suffix=None):
    url = u'http://testserver/api/v1/files/{}?filename={}'.format(
        attachment.pk, attachment.media_file.name)
    if suffix:
        url += u'?suffix={}'.format(suffix)

    return url


class TestMediaViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestMediaViewSet, self).setUp()
        self.retrieve_view = MediaViewSet.as_view({
            'get': 'retrieve'
        })

        self._publish_xls_form_to_project()
        self._submit_transport_instance_w_attachment()

    def test_retrieve_view(self):
        request = self.factory.get('/', {
            'filename': self.attachment.media_file.name}, **self.extra)
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'], attachment_url(self.attachment))

    @patch('onadata.apps.api.viewsets.media_viewset.image_url')
    def test_handle_image_exception(self, mock_image_url):
        mock_image_url.side_effect = Exception()
        request = self.factory.get(
            '/',
            {'filename': self.attachment.media_file.name, 'suffix': 'large'},
            **self.extra
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 400)

    def test_retrieve_view_small(self):
        request = self.factory.get(
            '/',
            {'filename': self.attachment.media_file.name, 'suffix': 'small'},
            **self.extra
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'],
                        attachment_url(self.attachment, 'small'))

    def test_retrieve_view_invalid_suffix(self):
        request = self.factory.get(
            '/',
            {'filename': self.attachment.media_file.name, 'suffix': 'TK'},
            **self.extra
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_invalid_pk(self):
        request = self.factory.get(
            '/',
            {'filename': self.attachment.media_file.name, 'suffix': 'small'},
            **self.extra
        )
        response = self.retrieve_view(request, 'INVALID')
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_no_filename_param(self):
        request = self.factory.get('/', **self.extra)
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_small_png(self):
        """Test retrieve png images"""
        s = 'transport_2011-07-25_19-05-49_1'
        media_file = "ona_png_image.png"

        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path, 'rb') as f:
            self._make_submission(os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml'), media_file=f)
        attachment = Attachment.objects.all().reverse()[0]
        self.attachment = attachment
        request = self.factory.get(
            '/',
            {'filename': self.attachment.media_file.name, 'suffix': 'small'},
            **self.extra
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'],
                        attachment_url(self.attachment, 'small'))
