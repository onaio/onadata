from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet


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
            'filename': self.attachment.media_file.name})
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'], attachment_url(self.attachment))

    def test_retrieve_view_small(self):
        request = self.factory.get('/', {
            'filename': self.attachment.media_file.name,
            'suffix': 'small'
        })
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'],
                        attachment_url(self.attachment, 'small'))

    def test_retrieve_view_invalid_suffix(self):
        request = self.factory.get('/', {
            'filename': self.attachment.media_file.name, 'suffix': 'TK'})
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_invalid_pk(self):
        request = self.factory.get('/', {
            'filename': self.attachment.media_file.name, 'suffix': 'small'})
        response = self.retrieve_view(request,  'INVALID')
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_no_filename_param(self):
        request = self.factory.get('/')
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 404)
