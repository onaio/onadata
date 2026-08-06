# -*- coding: utf-8 -*-
"""
Test attachments.
"""

import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponseRedirect
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIRequestFactory

from onadata.apps.logger.models import Attachment
from onadata.apps.logger.views import submission
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import show
from onadata.apps.viewer.views import attachment_url
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import EditorRole


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

    def _login_other_user(self, username="alice"):
        """Creates a second user with no role on the form and logs them in."""
        self._create_user(username, username)
        return self._login(username, username)

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

    def test_attachment_not_found_without_parameters(self):
        """A request with neither attachment_id nor media_file is a 404."""
        response = self.client.get(self.url)
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

    def test_anon_cannot_access_attachment_on_private_form(self):
        """Anonymous users are denied attachments of a form that is not shared."""
        self.assertFalse(self.xform.shared_data)
        response = self.anon.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 403)

    def test_other_user_cannot_access_attachment(self):
        """A user with no role on the form is denied its attachments."""
        alice = self._login_other_user()
        response = alice.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 403)

    def test_other_user_cannot_access_attachment_by_media_file(self):
        """The media_file lookup is authorized too, not just attachment_id."""
        alice = self._login_other_user()
        response = alice.get(self.url, {"media_file": self.attachment_media_file.name})
        self.assertEqual(response.status_code, 403)

    def test_anon_cannot_download_raw_bytes(self):
        """The no_redirect branch that streams raw bytes is gated too."""
        response = self.anon.get(
            self.url, {"attachment_id": self.attachment.id, "no_redirect": "true"}
        )
        self.assertEqual(response.status_code, 403)

    def test_meta_perms_restrict_collaborator_to_own_submissions(self):
        """With meta perms on, a collaborator cannot read others' attachments."""
        new_user = self._create_user("new_user", "new_user")
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )
        ShareXForm(self.xform, new_user.username, EditorRole.name).save()
        client = self._login("new_user", "new_user")
        response = client.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 403)

    def test_meta_perms_allow_collaborator_own_submission(self):
        """Meta perms still grant a collaborator their own attachment."""
        new_user = self._create_user("new_user", "new_user")
        self.attachment.user = new_user
        self.attachment.save()
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )
        ShareXForm(self.xform, new_user.username, EditorRole.name).save()
        client = self._login("new_user", "new_user")
        response = client.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 302)

    def test_public_link_bypasses_meta_perms(self):
        """A caller who followed the public link is not scoped by meta perms."""
        MetaData.public_link(self.xform, True)
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )
        alice = self._login_other_user()
        alice.get(reverse(show, kwargs={"uuid": self.xform.uuid}))
        response = alice.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 302)

    def test_anon_can_access_attachment_through_public_link(self):
        """The public link grants an anonymous caller the form's attachments."""
        MetaData.public_link(self.xform, True)
        self.anon.get(reverse(show, kwargs={"uuid": self.xform.uuid}))
        response = self.anon.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 302)

    def test_attachment_of_soft_deleted_form_is_not_served(self):
        """Attachments of a soft-deleted form are no longer downloadable."""
        self.xform.deleted_at = timezone.now()
        self.xform.save()
        response = self.client.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 404)

    def test_anon_can_access_attachment_on_shared_form(self):
        """Public access to a form whose data is shared is still allowed."""
        self.xform.shared_data = True
        self.xform.save()
        response = self.anon.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 302)

    def test_soft_deleted_attachment_is_not_served(self):
        """A soft-deleted attachment is no longer downloadable."""
        self.attachment.deleted_at = timezone.now()
        self.attachment.save()
        response = self.client.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 404)

    def test_attachment_of_soft_deleted_submission_is_not_served(self):
        """Attachments of a soft-deleted submission are no longer downloadable."""
        self.attachment.instance.deleted_at = timezone.now()
        self.attachment.instance.save()
        response = self.client.get(self.url, {"attachment_id": self.attachment.id})
        self.assertEqual(response.status_code, 404)
    @override_settings(
        STORAGES={
            "default": {"BACKEND": "storages.backends.azure_storage.AzureStorage"}
        },
        AZURE_ACCOUNT_NAME="test-account",
        AZURE_ACCOUNT_KEY="test-key",
        AZURE_CONTAINER="test-container",
    )
    @patch("azure.storage.blob.generate_blob_sas")
    def test_original_image_attachment_url_has_azure_sas_token(
        self, mock_generate_blob_sas
    ):
        """Test original image attachment url has azure sas token"""
        sas_token = "se=ab736fba7261"  # nosec
        mock_generate_blob_sas.return_value = sas_token
        expected_url = (
            "https://test-account.blob.core.windows.net/test-container/"
            f"{self.attachment_media_file.name}?{sas_token}"
        )

        response = self.client.get(
            self.url, {"media_file": self.attachment_media_file.name}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)
        self.assertIn(f"?{sas_token}", str(response.url))
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
