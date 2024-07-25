# -*- coding: utf-8 -*-
"""
Test attachments.
"""
import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponseRedirect
from django.urls import reverse

from rest_framework.test import APIRequestFactory

from onadata.apps.logger.models import Attachment
from onadata.apps.logger.views import submission
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.views import attachment_url


class TestAttachmentUrl(TestBase):
    """
    Test attachments.
    """

    def setUp(self):
        self.attachment_count = 0
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        self.url = reverse(attachment_url, kwargs={"size": "original"})
        self._submission_url = reverse(
            "submissions", kwargs={"username": self.user.username}
        )

    def test_attachment_url(self):
        self.assertEqual(Attachment.objects.count(), self.attachment_count + 1)
        response = self.client.get(
            self.url, {"media_file": self.attachment_media_file.name}
        )
        self.assertEqual(response.status_code, 302)  # redirects to amazon

    def test_attachment_url_no_redirect(self):
        self.assertEqual(Attachment.objects.count(), self.attachment_count + 1)
        response = self.client.get(
            self.url,
            {"media_file": self.attachment_media_file.name, "no_redirect": "true"},
        )
        self.assertEqual(response.status_code, 200)  # no redirects to amazon

    def test_attachment_not_found(self):
        response = self.client.get(
            self.url, {"media_file": "non_existent_attachment.jpg"}
        )
        self.assertEqual(response.status_code, 404)

    def test_attachment_has_mimetype(self):
        attachment = Attachment.objects.all().reverse()[0]
        self.assertEqual(attachment.mimetype, "image/jpeg")

    def test_attachment_url_w_media_id(self):
        """Test attachment url with attachment id"""
        self.assertEqual(Attachment.objects.count(), self.attachment_count + 1)
        response = self.client.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 302)  # redirects to amazon

    # pylint: disable=invalid-name
    def test_attachment_url_w_media_id_no_redirect(self):
        """Test attachment url with attachment id no redirect"""
        self.assertEqual(Attachment.objects.count(), self.attachment_count + 1)
        response = self.client.get(
            self.url, {"attachment_id": self.attachment.id, "no_redirect": "true"}
        )
        self.assertEqual(response.status_code, 200)  # no redirects to amazon

    @patch("onadata.apps.viewer.views.generate_media_download_url")
    def test_attachment_url_has_azure_sas_token(self, mock_media_url):
        """Test attachment url has azure sas token"""
        self._publish_xls_file(
            os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "transportation_encrypted.xlsx",
            )
        )
        files = {}
        for filename in ["submission.xml", "submission.xml.enc"]:
            files[filename] = os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "main",
                "tests",
                "fixtures",
                "transportation",
                "instances_encrypted",
                filename,
            )
        with open(files["submission.xml.enc"], "rb") as encryped_file:
            with open(files["submission.xml"], "rb") as f:
                post_data = {
                    "xml_submission_file": f,
                    "submission.xml.enc": encryped_file,
                }
                self.factory = APIRequestFactory()
                request = self.factory.post(self._submission_url, post_data)
                request.user = authenticate(username="bob", password="bob")
                response = submission(request, username=self.user.username)
                self.assertEqual(response.status_code, 201)

        # get submission enc attachment
        attachment = Attachment.objects.all()[1]
        sas_token = "se=ab736fba7261"  # nosec
        expected_url = f"http://testserver/{attachment.media_file.name}?{sas_token}"
        mock_media_url.return_value = HttpResponseRedirect(redirect_to=expected_url)
        response = self.client.get(self.url, {"media_file": attachment.media_file.name})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)
        self.assertIn(f"?{sas_token}", str(response.url))

    def tearDown(self):
        path = os.path.join(settings.MEDIA_ROOT, self.user.username)
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
