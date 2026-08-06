# -*- coding: utf-8 -*-
"""Test onadata.libs.utils.user_auth."""

from django.contrib.auth.models import AnonymousUser
from django.test.client import RequestFactory

from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import EditorRole
from onadata.libs.utils.user_auth import has_attachment_permission


class TestHasAttachmentPermission(TestBase):
    """Test has_attachment_permission()."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        self.factory = RequestFactory()

    def _request(self, user, session=None):
        request = self.factory.get(f"/media/{self.attachment.media_file.name}")
        request.user = user
        request.session = session if session is not None else {}
        return request

    def _enable_meta_perms(self):
        MetaData.xform_meta_permission(
            self.xform, data_value="editor-minor|dataentry-minor|readonly-no-download"
        )

    def test_owner_is_allowed(self):
        """The form owner may download the attachment."""
        request = self._request(self.user)
        self.assertTrue(has_attachment_permission(self.attachment, request))

    def test_anonymous_is_denied_on_private_form(self):
        """Anonymous callers are denied attachments of a private form."""
        request = self._request(AnonymousUser())
        self.assertFalse(has_attachment_permission(self.attachment, request))

    def test_user_without_role_is_denied(self):
        """A user with no role on the form is denied its attachments."""
        alice = self._create_user("alice", "alice")
        request = self._request(alice)
        self.assertFalse(has_attachment_permission(self.attachment, request))

    def test_anonymous_allowed_when_data_is_shared(self):
        """Attachments of a form whose data is public are open to anyone."""
        self.xform.shared_data = True
        self.xform.save()
        request = self._request(AnonymousUser())
        self.assertTrue(has_attachment_permission(self.attachment, request))

    def test_public_link_session_allows_anonymous(self):
        """A session that followed the public link admits an anonymous caller."""
        request = self._request(
            AnonymousUser(), session={"public_link": self.xform.uuid}
        )
        self.assertTrue(has_attachment_permission(self.attachment, request))

    def test_public_link_session_bypasses_meta_perms_for_logged_in_user(self):
        """A logged-in caller who followed the public link is not scoped by
        meta perms, just like an anonymous one."""
        self._enable_meta_perms()
        alice = self._create_user("alice", "alice")
        request = self._request(alice, session={"public_link": self.xform.uuid})
        self.assertTrue(has_attachment_permission(self.attachment, request))

    def test_meta_perms_restrict_collaborator_to_own_submissions(self):
        """With meta perms on, a collaborator cannot read others' attachments."""
        self._enable_meta_perms()
        collaborator = self._create_user("collaborator", "collaborator")
        ShareXForm(self.xform, collaborator.username, EditorRole.name).save()
        request = self._request(collaborator)
        self.assertFalse(has_attachment_permission(self.attachment, request))

    def test_meta_perms_allow_collaborator_own_submission(self):
        """Meta perms still grant a collaborator their own attachment."""
        collaborator = self._create_user("collaborator", "collaborator")
        self.attachment.user = collaborator
        self.attachment.save()
        self._enable_meta_perms()
        ShareXForm(self.xform, collaborator.username, EditorRole.name).save()
        request = self._request(collaborator)
        self.assertTrue(has_attachment_permission(self.attachment, request))

    def test_request_without_session_is_handled(self):
        """A request object with no session attribute does not error."""
        request = self.factory.get(f"/media/{self.attachment.media_file.name}")
        request.user = self.user
        self.assertTrue(has_attachment_permission(self.attachment, request))

    def test_falls_back_to_instance_xform(self):
        """The form is resolved through the submission when the denormalised
        ``xform`` field is unset."""
        self.attachment.xform = None
        self.attachment.save()
        self.assertTrue(
            has_attachment_permission(self.attachment, self._request(self.user))
        )
        alice = self._create_user("alice", "alice")
        self.assertFalse(
            has_attachment_permission(self.attachment, self._request(alice))
        )
