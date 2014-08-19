from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.attachment_viewset import AttachmentViewSet


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
        self._submit_transport_instance_w_attachment()

    def test_retrieve_view(self):
        pk = self.attachment.pk
        data = {
            "instance": "http://testserver/api/v1/data/%s/%s"
            % (self.xform.pk, self.attachment.instance.pk),
            "id": pk,
            "media_file": self.attachment.media_file.name,
            "mimetype": self.attachment.mimetype
        }
        request = self.factory.get('/', **self.extra)
        response = self.retrieve_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, dict))
        self.assertEqual(response.data, data)

    def test_list_view(self):
        request = self.factory.get('/', **self.extra)
        response = self.list_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
