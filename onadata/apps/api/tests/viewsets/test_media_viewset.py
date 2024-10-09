# -*- coding: utf-8 -*-
"""
Tests the MediaViewSet.
"""
# pylint: disable=too-many-lines
import os
from unittest.mock import patch

from django.utils import timezone

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.media_viewset import MediaViewSet
from onadata.apps.logger.models import Attachment
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import EditorRole


def attachment_url(attachment, suffix=None):
    url = "http://testserver/api/v1/files/{}?filename={}".format(
        attachment.pk, attachment.media_file.name
    )
    if suffix:
        url += "?suffix={}".format(suffix)

    return url


class TestMediaViewSet(TestAbstractViewSet, TestBase):
    """
    Test the /api/v1/files endpoint
    """

    def setUp(self):
        super().setUp()
        self.retrieve_view = MediaViewSet.as_view({"get": "retrieve"})

        self._publish_xls_form_to_project()
        self._submit_transport_instance_w_attachment()

    def test_retrieve_view(self):
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 200, response)
        self.assertEqual(type(response.content), bytes)

        # test when the submission is soft deleted
        self.attachment.instance.deleted_at = timezone.now()
        self.attachment.instance.save()

        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 404, response)

    def test_anon_retrieve_view(self):
        """Test that anonymous users shouldn't retrieve media"""
        request = self.factory.get("/", {"filename": self.attachment.media_file.name})
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 404, response)

    def test_retrieve_no_perms(self):
        """Test that users without permissions to retrieve media
        shouldn't be able to retrieve media
        """
        # create new user
        new_user = self._create_user("new_user", "new_user")
        self.extra = {"HTTP_AUTHORIZATION": f"Token {new_user.auth_token.key}"}
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        self.assertTrue(new_user.is_authenticated)
        response = self.retrieve_view(request, pk=self.attachment.pk)
        # new user shouldn't have perms to download media
        self.assertEqual(response.status_code, 404, response)

    def test_returned_media_is_based_on_form_perms(self):
        """Test that attachments are returned based on form meta permissions"""
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 200, response)
        self.assertEqual(type(response.content), bytes)

        # Enable meta perms
        new_user = self._create_user("new_user", "new_user")
        data_value = "editor-minor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        instance = ShareXForm(self.xform, new_user.username, EditorRole.name)
        instance.save()
        auth_extra = {"HTTP_AUTHORIZATION": f"Token {new_user.auth_token.key}"}

        # New user should not be able to view media for
        # submissions which they did not submit
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **auth_extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    @patch("onadata.libs.utils.image_tools.get_storages_media_download_url")
    def test_retrieve_view_from_s3(self, mock_download_url):
        expected_url = (
            "https://testing.s3.amazonaws.com/doe/attachments/"
            "4_Media_file/media.png?"
            "response-content-disposition=attachment%3Bfilename%3media.png&"
            "response-content-type=application%2Foctet-stream&"
            "AWSAccessKeyId=AKIAJ3XYHHBIJDL7GY7A"
            "&Signature=aGhiK%2BLFVeWm%2Fmg3S5zc05g8%3D&Expires=1615554960"
        )
        mock_download_url.return_value = expected_url
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)
        filename = self.attachment.media_file.name.split("/")[-1]
        mock_download_url.assert_called_once_with(
            self.attachment.media_file.name, f'attachment; filename="{filename}"', 3600
        )

    @patch("onadata.libs.utils.image_tools.get_storages_media_download_url")
    def test_anon_retrieve_view_from_s3(self, mock_download_url):
        """Test that anonymous user cannot retrieve media from s3"""
        expected_url = (
            "https://testing.s3.amazonaws.com/doe/attachments/"
            "4_Media_file/media.png?"
            "response-content-disposition=attachment%3Bfilename%3media.png&"
            "response-content-type=application%2Foctet-stream&"
            "AWSAccessKeyId=AKIAJ3XYHHBIJDL7GY7A"
            "&Signature=aGhiK%2BLFVeWm%2Fmg3S5zc05g8%3D&Expires=1615554960"
        )
        mock_download_url.return_value = expected_url
        request = self.factory.get("/", {"filename": self.attachment.media_file.name})
        response = self.retrieve_view(request, pk=self.attachment.pk)

        self.assertEqual(response.status_code, 404, response)

    @patch("onadata.libs.utils.image_tools.get_storages_media_download_url")
    def test_retrieve_view_from_s3_no_perms(self, mock_download_url):
        """Test that authenticated user without correct perms
        cannot retrieve media from s3
        """
        expected_url = (
            "https://testing.s3.amazonaws.com/doe/attachments/"
            "4_Media_file/media.png?"
            "response-content-disposition=attachment%3Bfilename%3media.png&"
            "response-content-type=application%2Foctet-stream&"
            "AWSAccessKeyId=AKIAJ3XYHHBIJDL7GY7A"
            "&Signature=aGhiK%2BLFVeWm%2Fmg3S5zc05g8%3D&Expires=1615554960"
        )
        mock_download_url.return_value = expected_url
        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        # owner should be able to retrieve media
        self.assertEqual(response.status_code, 302, response)

        # create new user
        new_user = self._create_user("new_user", "new_user")
        self.extra = {"HTTP_AUTHORIZATION": f"Token {new_user.auth_token.key}"}

        request = self.factory.get(
            "/", {"filename": self.attachment.media_file.name}, **self.extra
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        # new user shouldn't have perms to download media
        self.assertEqual(response.status_code, 404, response)

    def test_retrieve_view_with_suffix(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "large"},
            **self.extra,
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
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
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 400)

    def test_retrieve_view_small(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "small"},
            **self.extra,
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"], attachment_url(self.attachment, "small"))

    def test_retrieve_view_invalid_suffix(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "TK"},
            **self.extra,
        )
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_invalid_pk(self):
        request = self.factory.get(
            "/",
            {"filename": self.attachment.media_file.name, "suffix": "small"},
            **self.extra,
        )
        response = self.retrieve_view(request, pk="INVALID")
        self.assertEqual(response.status_code, 404)

    def test_retrieve_view_no_filename_param(self):
        request = self.factory.get("/", **self.extra)
        response = self.retrieve_view(request, pk=self.attachment.pk)
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
        response = self.retrieve_view(request, pk=self.attachment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"], attachment_url(self.attachment, "small"))
