# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on form metadata that grants roles, publishes a
form, or says where TextIt posts submissions.
"""

from onadata.apps.api.tests.viewsets.test_stepup_form_and_transfer_gates import (
    GateTestCase,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    EDITOR_BECOMES_MANAGER,
    EDITOR_BECOMES_OWNER,
    EDITOR_STAYS_BELOW_ADMIN,
    gating,
)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.main.models import MetaData
from onadata.libs.permissions import (
    EditorMinorRole,
    EditorRole,
    ManagerRole,
    OwnerRole,
)
from onadata.libs.serializers.metadata_serializer import (
    create_xform_meta_permissions,
)
from onadata.libs.stepup.policy import (
    GATE_CHANGE_WEBHOOK,
    GATE_PUBLISH_DATA,
    GATE_SHARE_FORM_ADMIN,
)
from onadata.libs.utils.common_tags import TEXTIT, XFORM_META_PERMS

DEFAULT_META_PERMS = "editor|dataentry|readonly"
TEXTIT_SETTINGS = "token|flow-uuid|contact-uuid"
OTHER_TEXTIT_SETTINGS = "other-token|flow-uuid|contact-uuid"


class MetaDataGateTestCase(GateTestCase):
    """A published form and requests against its metadata."""

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()

    def _create(self, data_type, data_value, headers=None):
        view = MetaDataViewSet.as_view({"post": "create"})
        data = {
            "data_type": data_type,
            "data_value": data_value,
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data=data, **{**self.extra, **(headers or {})})
        return view(request)

    def _update(self, metadata, data, headers=None, method="put"):
        view = MetaDataViewSet.as_view({"put": "update", "patch": "partial_update"})
        request = getattr(self.factory, method)(
            "/",
            data={"xform": self.xform.pk, **data},
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=metadata.pk)


@gating(GATE_SHARE_FORM_ADMIN)
class TestMetaPermsGate(MetaDataGateTestCase):
    """Meta permissions give a form's editors the role in their slot, so a
    stolen session must not be able to name owner or manager there."""

    audience = GATE_SHARE_FORM_ADMIN

    def setUp(self):
        super().setUp()
        self.alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        EditorRole.add(self.alice, self.xform)
        # Publishing gives every form this row, so a create updates it.
        self.assertEqual(self._meta_perms().data_value, DEFAULT_META_PERMS)

    def _meta_perms(self):
        return MetaData.xform_meta_permission(self.xform)

    def test_naming_owner_in_a_slot_is_challenged(self):
        """The 401 names the audience, nothing is stored and the editor
        stays an editor."""
        response = self._create(XFORM_META_PERMS, EDITOR_BECOMES_OWNER)

        self.assert_challenged(response)
        self.assertEqual(self._meta_perms().data_value, DEFAULT_META_PERMS)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.xform))

    def test_a_grant_makes_the_editor_an_owner(self):
        """With a grant the meta permissions are stored and applied."""
        grant = self._grant()

        response = self._create(
            XFORM_META_PERMS, EDITOR_BECOMES_OWNER, self._with_grant(grant)
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._meta_perms().data_value, EDITOR_BECOMES_OWNER)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))
        self.assert_spent(grant)

    def test_meta_perms_without_an_admin_slot_are_not_challenged(self):
        """No slot names owner or manager, so nobody becomes an admin."""
        self.assert_challenged(self._create(XFORM_META_PERMS, EDITOR_BECOMES_OWNER))

        response = self._create(XFORM_META_PERMS, EDITOR_STAYS_BELOW_ADMIN)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(EditorMinorRole.user_has_role(self.alice, self.xform))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.xform))

    def test_raising_a_slot_to_owner_is_challenged(self):
        """An update is gated too, and a manager slot raised to owner
        appoints owners."""
        metadata = MetaData.xform_meta_permission(
            self.xform, data_value=EDITOR_BECOMES_MANAGER
        )

        response = self._update(
            metadata, {"data_value": EDITOR_BECOMES_OWNER}, method="patch"
        )

        self.assert_challenged(response)
        metadata.refresh_from_db()
        self.assertEqual(metadata.data_value, EDITOR_BECOMES_MANAGER)

    def test_keeping_an_admin_slot_is_not_challenged(self):
        """Writing back a slot that already names manager, applied to every
        editor, appoints nobody new."""
        applied_admin_slot = "manager|dataentry|readonly"
        metadata = create_xform_meta_permissions(applied_admin_slot, self.xform)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assert_challenged(
            self._update(metadata, {"data_value": EDITOR_BECOMES_OWNER}, method="patch")
        )

        response = self._update(
            metadata,
            {"data_type": XFORM_META_PERMS, "data_value": applied_admin_slot},
        )

        self.assertEqual(response.status_code, 200, response.data)
        metadata.refresh_from_db()
        self.assertEqual(metadata.data_value, applied_admin_slot)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.xform))

    def test_writing_back_a_slot_that_promotes_an_editor_is_challenged(self):
        """Every write applies the value to all the form's users, so an
        unchanged one still appoints an editor it has not reached yet."""
        unapplied_admin_slot = "manager|dataentry|readonly"
        metadata = MetaData.xform_meta_permission(
            self.xform, data_value=unapplied_admin_slot
        )
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))

        response = self._update(
            metadata,
            {"data_type": XFORM_META_PERMS, "data_value": unapplied_admin_slot},
        )

        self.assert_challenged(response)
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))

    def test_a_grant_lets_a_promoting_write_back_through(self):
        """With a grant the unchanged value is applied and the editor becomes
        a manager."""
        unapplied_admin_slot = "manager|dataentry|readonly"
        metadata = MetaData.xform_meta_permission(
            self.xform, data_value=unapplied_admin_slot
        )
        grant = self._grant()

        response = self._update(
            metadata,
            {"data_type": XFORM_META_PERMS, "data_value": unapplied_admin_slot},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assert_spent(grant)

    def test_an_invalid_value_keeps_the_grant(self):
        """Validation comes first, so a malformed value does not spend it."""
        self.assert_challenged(self._create(XFORM_META_PERMS, EDITOR_BECOMES_OWNER))
        grant = self._grant()

        response = self._create(
            XFORM_META_PERMS, "owner|not-a-role", self._with_grant(grant)
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unspent(grant)
        self.assertEqual(self._meta_perms().data_value, DEFAULT_META_PERMS)


@gating(GATE_PUBLISH_DATA)
class TestPublicLinkGate(MetaDataGateTestCase):
    """A public link lets anyone holding it read the form, so a stolen session
    must not be able to turn one on."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        self.assertFalse(MetaData.public_link(self.xform))

    def test_turning_on_a_public_link_is_challenged(self):
        """The 401 names the audience and the link stays off."""
        response = self._create("public_link", "True")

        self.assert_challenged(response)
        self.assertFalse(MetaData.public_link(self.xform))

    def test_a_grant_turns_the_link_on(self):
        """With a grant the link is on."""
        grant = self._grant()

        response = self._create("public_link", "True", self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(MetaData.public_link(self.xform))
        self.assert_spent(grant)

    def test_turning_a_link_on_by_update_is_challenged(self):
        """An update that flips an off link on is gated too."""
        MetaData.public_link(self.xform, False)
        metadata = MetaData.objects.get(data_type="public_link")

        response = self._update(
            metadata, {"data_type": "public_link", "data_value": "True"}
        )

        self.assert_challenged(response)
        metadata.refresh_from_db()
        self.assertEqual(metadata.data_value, "False")

    def test_turning_a_link_off_is_not_challenged(self):
        """Withdrawing the link publishes nothing."""
        self.assert_challenged(self._create("public_link", "True"))

        response = self._create("public_link", "False")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(MetaData.public_link(self.xform))

    def test_rewriting_an_on_link_is_not_challenged(self):
        """A link that is already on publishes nothing new."""
        MetaData.public_link(self.xform, False)
        metadata = MetaData.objects.get(data_type="public_link")
        self.assert_challenged(
            self._update(metadata, {"data_type": "public_link", "data_value": "True"})
        )
        MetaData.public_link(self.xform, True)
        self.assertTrue(MetaData.public_link(self.xform))

        response = self._update(
            metadata, {"data_type": "public_link", "data_value": "True"}
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(MetaData.public_link(self.xform))


@gating(GATE_CHANGE_WEBHOOK)
class TestTextItSettingsGate(MetaDataGateTestCase):
    """A form's TextIt service posts submissions with the token and contacts
    in its metadata, the same reach the webhook gate protects."""

    audience = GATE_CHANGE_WEBHOOK

    def setUp(self):
        super().setUp()
        self.assertIsNone(MetaData.textit(self.xform))

    def test_setting_textit_is_challenged(self):
        """The 401 names the audience and nothing is stored."""
        response = self._create(TEXTIT, TEXTIT_SETTINGS)

        self.assert_challenged(response)
        self.assertIsNone(MetaData.textit(self.xform))

    def test_a_grant_lets_textit_be_set(self):
        """With a grant the settings are stored."""
        grant = self._grant()

        response = self._create(TEXTIT, TEXTIT_SETTINGS, self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(MetaData.textit(self.xform), TEXTIT_SETTINGS)
        self.assert_spent(grant)

    def test_changing_textit_is_challenged(self):
        """An update to other settings is gated and leaves them as they
        were."""
        MetaData.textit(self.xform, data_value=TEXTIT_SETTINGS)
        metadata = MetaData.objects.get(data_type=TEXTIT)

        response = self._update(
            metadata, {"data_type": TEXTIT, "data_value": OTHER_TEXTIT_SETTINGS}
        )

        self.assert_challenged(response)
        self.assertEqual(MetaData.textit(self.xform), TEXTIT_SETTINGS)

    def test_writing_back_the_same_settings_is_not_challenged(self):
        """Unchanged settings send nothing anywhere new."""
        MetaData.textit(self.xform, data_value=TEXTIT_SETTINGS)
        metadata = MetaData.objects.get(data_type=TEXTIT)
        self.assert_challenged(
            self._update(
                metadata, {"data_type": TEXTIT, "data_value": OTHER_TEXTIT_SETTINGS}
            )
        )

        response = self._update(
            metadata, {"data_type": TEXTIT, "data_value": TEXTIT_SETTINGS}
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(MetaData.textit(self.xform), TEXTIT_SETTINGS)
