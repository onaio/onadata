import os
import urllib
from mock import MagicMock, patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet
from onadata.apps.logger.models import Attachment


def attachment_url(attachment, suffix=None):
    url = "http://testserver/api/v1/files/{}?filename={}".format(
        attachment.pk, attachment.media_file.name
    )
    if suffix:
        url += "?suffix={}".format(suffix)

    return url


class TestMediaViewSet(TestAbstractViewSet):
    """
    Test the /api/v1/files endpoint
    """
    def setUp(self):
        super(TestMediaViewSet, self).setUp()
        self.retrieve_view = MediaViewSet.as_view({"get": "retrieve"})

        self._publish_xls_form_to_project()
        self._submit_transport_instance_w_attachment()

    def test_retrieve_view(self):
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 200, response)
        self.assertEqual(type(response.content), bytes)

    @patch("onadata.libs.utils.image_tools.get_storage_class")
    @patch("onadata.libs.utils.image_tools.boto3.client")
    def test_retrieve_view_from_s3(self, mock_presigned_urls, mock_get_storage_class):

        expected_url = (
            "https://testing.s3.amazonaws.com/doe/attachments/"
            "4_Media_file/media.png?"
            "response-content-disposition=attachment%3Bfilename%3media.png&"
            "response-content-type=application%2Foctet-stream&"
            "AWSAccessKeyId=AKIAJ3XYHHBIJDL7GY7A"
            "&Signature=aGhiK%2BLFVeWm%2Fmg3S5zc05g8%3D&Expires=1615554960"
        )
        mock_presigned_urls().generate_presigned_url = MagicMock(
            return_value=expected_url
        )
        mock_get_storage_class()().bucket.name = "onadata"
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, self.attachment.pk)

        self.assertEqual(response.status_code, 302, response.url)
        self.assertEqual(response.url, expected_url)
        self.assertTrue(mock_presigned_urls.called)
        filename = self.attachment.media_file.name.split("/")[-1]
        mock_presigned_urls().generate_presigned_url.assert_called_with(
            "get_object",
            Params={
                "Bucket": "onadata",
                "Key": self.attachment.media_file.name,
                "ResponseContentDisposition": urllib.parse.quote(
                    f"attachment; filename={filename}"
                ),
                "ResponseContentType": "application/octet-stream",
            },
            ExpiresIn=3600,
        )

    def test_retrieve_view_with_suffix(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "large"},
            **self.extra,
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"], attachment_url(self.attachment))

    @patch("onadata.apps.api.viewsets.media_viewset.image_url")
    def test_handle_image_exception(self, mock_image_url):
        mock_image_url.side_effect = Exception()
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "large"},
            **self.extra,
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 400)

    def test_retrieve_view_small(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "small"},
            **self.extra,
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"], attachment_url(self.attachment, "small"))

    def test_retrieve_view_invalid_suffix(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "TK"},
            **self.extra,
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_invalid_pk(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "small"},
            **self.extra,
        )
        response = self.retrieve_view(request, "INVALID")
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_no_filename_param(self):
        request = self.factory.get("/", **self.extra)
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_small_png(self):
        """Test retrieve png images"""
        s = "transport_2011-07-25_19-05-49_1"
        media_file = "ona_png_image.png"

        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            self._make_submission(
                os.path.join(
                    self.main_directory,
                    "fixtures",
                    "transportation",
                    "instances",
                    s,
                    s + ".xml",
                ),
                media_file=f,
            )
        attachment = Attachment.objects.all().reverse()[0]
        self.attachment = attachment
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "small"},
            **self.extra,
        )
        response = self.retrieve_view(request, self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"], attachment_url(self.attachment, "small"))
