# -*- coding: utf-8 -*-
"""
Tests for permission-enforced serving of MEDIA_ROOT files at /media/<path>.

Every file under MEDIA_ROOT belongs to a known owner object — a submission
attachment (plus its image thumbnails), an XLSForm file, a form media/doc
MetaData file or an export. Serving any of them must first pass that object's
permission checks, and paths that resolve to no known object must not be
served at all.
"""

import os

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile, File
from django.core.files.storage import storages
from django.urls import reverse
from django.utils import timezone

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import show
from onadata.apps.viewer.models.export import Export
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import EditorRole
from onadata.libs.utils.viewer_tools import get_path


class ServeMediaTestBase(TestBase):
    """Shared helpers for the /media/<path> serving tests."""

    def _get_media(self, path, client=None):
        client = client or self.client
        return client.get(f"/media/{path}")

    def _login_stranger(self, username="alice"):
        """Creates a second user with no role on the form and logs them in."""
        self._create_user(username, username)
        return self._login(username, username)

    def _response_bytes(self, response):
        if response.streaming:
            return b"".join(response.streaming_content)
        return response.content


class TestServeAttachmentMedia(ServeMediaTestBase):
    """Submission attachments and their thumbnails."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        self.path = self.attachment.media_file.name

    def test_anonymous_is_denied(self):
        """Anonymous users cannot fetch attachments of a private form."""
        self.assertFalse(self.xform.shared_data)
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 403)

    def test_user_without_role_is_denied(self):
        """A user with no role on the form cannot fetch its attachments."""
        stranger = self._login_stranger()
        response = self._get_media(self.path, stranger)
        self.assertEqual(response.status_code, 403)

    def test_owner_downloads_attachment(self):
        """The form owner can still download the attachment bytes."""
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 200)
        with self.attachment.media_file.open("rb") as media_file:
            self.assertEqual(self._response_bytes(response), media_file.read())

    def test_anonymous_allowed_when_data_is_shared(self):
        """Attachments of a form whose data is public remain reachable."""
        self.xform.shared_data = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 200)

    def test_thumbnail_requires_attachment_permission(self):
        """A thumbnail path is authorized against its parent attachment."""
        thumbnail_path = get_path(self.path, "-small")
        response = self._get_media(thumbnail_path, self.anon)
        self.assertEqual(response.status_code, 403)

    def test_owner_downloads_thumbnail(self):
        """The form owner can fetch a generated thumbnail."""
        default_storage = storages["default"]
        thumbnail_path = get_path(self.path, "-small")
        if default_storage.exists(thumbnail_path):
            default_storage.delete(thumbnail_path)
        default_storage.save(thumbnail_path, ContentFile(b"thumbnail-bytes"))
        response = self._get_media(thumbnail_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._response_bytes(response), b"thumbnail-bytes")

    def test_soft_deleted_attachment_is_not_served(self):
        """A soft-deleted attachment is gone even for the owner."""
        self.attachment.deleted_at = timezone.now()
        self.attachment.save()
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 404)

    def test_attachment_of_deleted_form_is_not_served(self):
        """Attachments of a soft-deleted form are gone even for the owner."""
        self.xform.deleted_at = timezone.now()
        self.xform.save()
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 404)

    def test_meta_perms_restrict_collaborator_to_own_submissions(self):
        """With meta perms on, a collaborator cannot read others' attachments."""
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )
        self._create_user("collaborator", "collaborator")
        ShareXForm(self.xform, "collaborator", EditorRole.name).save()
        collaborator = self._login("collaborator", "collaborator")
        response = self._get_media(self.path, collaborator)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_allowed_through_public_link(self):
        """The public link grants an anonymous caller the form's attachments."""
        MetaData.public_link(self.xform, True)
        self.anon.get(reverse(show, kwargs={"uuid": self.xform.uuid}))
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 200)

    def test_public_link_bypasses_meta_perms_for_logged_in_user(self):
        """A logged-in caller who followed the public link is not scoped by
        meta perms, just like an anonymous one."""
        MetaData.public_link(self.xform, True)
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )
        stranger = self._login_stranger()
        stranger.get(reverse(show, kwargs={"uuid": self.xform.uuid}))
        response = self._get_media(self.path, stranger)
        self.assertEqual(response.status_code, 200)


class TestServeXLSFormMedia(ServeMediaTestBase):
    """Uploaded XLSForm files."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self.path = self.xform.xls.name

    def test_anonymous_is_denied(self):
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 403)

    def test_user_without_role_is_denied(self):
        stranger = self._login_stranger()
        response = self._get_media(self.path, stranger)
        self.assertEqual(response.status_code, 403)

    def test_owner_downloads_xlsform(self):
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 200)
        with self.xform.xls.open("rb") as xls_file:
            self.assertEqual(self._response_bytes(response), xls_file.read())

    def test_anonymous_allowed_when_form_is_public(self):
        """The form definition of a publicly shared form stays reachable."""
        self.xform.shared = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 200)

    def test_xlsform_of_deleted_form_is_not_served(self):
        self.xform.deleted_at = timezone.now()
        self.xform.save()
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 404)


class TestServeMetaDataMedia(ServeMediaTestBase):
    """Form media files attached through MetaData."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        fixture_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "screenshot.png"
        )
        with open(fixture_path, "rb") as media_file:
            self.metadata = MetaData.objects.create(
                content_type=ContentType.objects.get_for_model(XForm),
                object_id=self.xform.id,
                data_type="media",
                data_value="screenshot.png",
                data_file=File(media_file, "screenshot.png"),
                data_file_type="image/png",
            )
        self.path = self.metadata.data_file.name

    def test_anonymous_is_denied(self):
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 403)

    def test_user_without_role_is_denied(self):
        stranger = self._login_stranger()
        response = self._get_media(self.path, stranger)
        self.assertEqual(response.status_code, 403)

    def test_owner_downloads_form_media(self):
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 200)
        with self.metadata.data_file.open("rb") as media_file:
            self.assertEqual(self._response_bytes(response), media_file.read())

    def test_owner_response_uses_original_filename(self):
        """Unsigned metadata responses use the display filename."""
        self.metadata.data_value = "apple.jpg"
        self.metadata.save(update_fields=["data_value"])

        response = self._get_media(self.path)

        self.assertNotEqual(os.path.basename(self.path), "apple.jpg")
        self.assertEqual(
            response["Content-Disposition"], 'inline; filename="apple.jpg"'
        )

    def test_supporting_document_response_uses_original_filename(self):
        """Unsigned supporting documents use the display filename."""
        fixture_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "screenshot.png"
        )
        with open(fixture_path, "rb") as media_file:
            metadata = MetaData.objects.create(
                content_type=ContentType.objects.get_for_model(XForm),
                object_id=self.xform.id,
                data_type="supporting_doc",
                data_value="apple.jpg",
                data_file=File(media_file, "random-storage-key.jpg"),
                data_file_type="image/jpeg",
            )

        response = self._get_media(metadata.data_file.name)

        self.assertNotEqual(
            os.path.basename(metadata.data_file.name), metadata.data_value
        )
        self.assertEqual(
            response["Content-Disposition"], 'inline; filename="apple.jpg"'
        )

    def test_anonymous_allowed_when_form_is_public(self):
        """Media of a publicly shared form stays reachable to data collectors."""
        self.xform.shared = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 200)

    def test_soft_deleted_metadata_is_not_served(self):
        self.metadata.deleted_at = timezone.now()
        self.metadata.save()
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 404)


class TestServeExportMedia(ServeMediaTestBase):
    """Generated export files."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        default_storage = storages["default"]
        file_path = os.path.join(
            self.user.username, "exports", self.xform.id_string, "csv", "export.csv"
        )
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
        self.path = default_storage.save(file_path, ContentFile(b"col\nvalue\n"))
        filedir, filename = os.path.split(self.path)
        self.export = Export.objects.create(
            xform=self.xform,
            export_type=Export.CSV_EXPORT,
            filedir=filedir,
            filename=filename,
        )

    def test_anonymous_is_denied(self):
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 403)

    def test_user_without_role_is_denied(self):
        stranger = self._login_stranger()
        response = self._get_media(self.path, stranger)
        self.assertEqual(response.status_code, 403)

    def test_owner_downloads_export(self):
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._response_bytes(response), b"col\nvalue\n")

    def test_anonymous_allowed_when_data_is_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 200)

    def test_export_of_deleted_form_is_not_served(self):
        self.xform.deleted_at = timezone.now()
        self.xform.save()
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 404)

    def test_editor_downloads_export(self):
        """A collaborator with access to all of the form's data is allowed."""
        self._create_user("editor", "editor")
        ShareXForm(self.xform, "editor", EditorRole.name).save()
        editor = self._login("editor", "editor")
        response = self._get_media(self.path, editor)
        self.assertEqual(response.status_code, 200)

    def test_meta_perms_restricted_collaborator_is_denied(self):
        """A collaborator scoped to their own submissions cannot download
        a whole-form export, matching what ExportFilter enforces."""
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )
        self._create_user("collaborator", "collaborator")
        ShareXForm(self.xform, "collaborator", EditorRole.name).save()
        collaborator = self._login("collaborator", "collaborator")
        response = self._get_media(self.path, collaborator)
        self.assertEqual(response.status_code, 403)

    def test_submitter_scoped_export_is_only_served_to_the_submitter(self):
        """An export filtered by _submitted_by is private to that submitter."""
        self.export.options = {"query": {"_submitted_by": "collaborator"}}
        self.export.save()
        self._create_user("collaborator", "collaborator")
        ShareXForm(self.xform, "collaborator", EditorRole.name).save()
        collaborator = self._login("collaborator", "collaborator")
        self.assertEqual(self._get_media(self.path, collaborator).status_code, 200)
        # not even the form owner sees another user's scoped export
        self.assertEqual(self._get_media(self.path).status_code, 403)

    def test_submitter_scoped_export_is_not_public(self):
        """Sharing a form's data does not expose submitter-scoped exports."""
        self.export.options = {"query": {"_submitted_by": "collaborator"}}
        self.export.save()
        self.xform.shared_data = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 403)


class TestServeInstanceMetaDataMedia(ServeMediaTestBase):
    """Submission documents attached through MetaData."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form_and_submit_instance()
        self.instance = self.xform.instances.first()
        fixture_path = os.path.join(
            self.this_directory, "fixtures", "transportation", "screenshot.png"
        )
        with open(fixture_path, "rb") as media_file:
            self.metadata = MetaData.objects.create(
                content_type=ContentType.objects.get_for_model(Instance),
                object_id=self.instance.id,
                data_type="media",
                data_value="screenshot.png",
                data_file=File(media_file, "screenshot.png"),
                data_file_type="image/png",
            )
        self.path = self.metadata.data_file.name

    def test_anonymous_denied_when_only_the_form_is_public(self):
        """A publicly listed form does not expose submission documents."""
        self.xform.shared = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 403)

    def test_owner_downloads_submission_document(self):
        response = self._get_media(self.path)
        self.assertEqual(response.status_code, 200)
        with self.metadata.data_file.open("rb") as media_file:
            self.assertEqual(self._response_bytes(response), media_file.read())

    def test_user_without_role_is_denied(self):
        stranger = self._login_stranger()
        response = self._get_media(self.path, stranger)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_allowed_when_data_is_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        response = self._get_media(self.path, self.anon)
        self.assertEqual(response.status_code, 200)


class TestServeUnknownMedia(ServeMediaTestBase):
    """Paths that resolve to no known owner object are never served."""

    def test_unresolvable_file_on_disk_is_not_served(self):
        """A MEDIA_ROOT file with no owning database record is not served."""
        default_storage = storages["default"]
        file_path = os.path.join(self.user.username, "csv_imports", "import.csv")
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
        saved_path = default_storage.save(file_path, ContentFile(b"a,b\n1,2\n"))
        self.assertEqual(self._get_media(saved_path).status_code, 404)
        self.assertEqual(self._get_media(saved_path, self.anon).status_code, 404)

    def test_missing_file_is_not_served(self):
        response = self._get_media("no/such/file.png", self.anon)
        self.assertEqual(response.status_code, 404)
