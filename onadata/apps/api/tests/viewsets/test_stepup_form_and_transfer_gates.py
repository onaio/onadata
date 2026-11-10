# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on transferring a project, on weakening a form's
protection, and on publishing a form's data by moving it into a public
project or by opening an open-data link to it.

Every test that expects a request through first shows that the gate is
active, so removing the gate fails it too.
"""

import json
import os

from django.conf import settings
from django.test.utils import override_settings

from oidc.stepup_grants import spend_grant

from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.v2.project_viewset import (
    ProjectViewSet as ProjectViewSetV2,
)
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import OpenData, Project, XForm
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.libs.stepup.policy import (
    GATE_DISABLE_FORM_ENCRYPTION,
    GATE_FORM_REQUIRE_AUTH,
    GATE_PUBLISH_DATA,
    GATE_TRANSFER_PROJECT,
)

ONE_GATED_CHANGE = "one_gated_change_per_request"


def gating_together(*audiences):
    """Gate every one of ``audiences``, for a user with a confirmed factor."""
    return override_settings(
        STEP_UP={
            "MODE": "local",
            "ACTIONS": list(audiences),
            "NO_FACTOR_POLICY": "skip_gate",
        }
    )


class GateTestCase(StepUpGateTestCase):
    """Adds the refusal of a request that makes two gated changes."""

    def assert_one_gated_change(self, response, audiences):
        """Refused before any grant was spent, naming every gated change."""
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["error"], ONE_GATED_CHANGE)
        self.assertCountEqual(response.data["audiences"], audiences)

    def assert_unspent(self, grant):
        """The request left ``grant`` for a later one."""
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))

    def _patch_form(self, data, headers=None):
        view = XFormViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, **{**self.extra, **(headers or {})}
        )
        return view(request, pk=self.xform.pk)


@gating(GATE_TRANSFER_PROJECT)
class TestTransferProjectGate(GateTestCase):
    """Moving a project to another account hands that account's admins its
    forms and data, so a stolen session must not be able to do it."""

    audience = GATE_TRANSFER_PROJECT

    def setUp(self):
        super().setUp()
        self._project_create()
        self._org_create()
        self.org_user = self.organization.user
        self.org_url = f"http://testserver/api/v1/users/{self.org_user.username}"
        self.user_url = f"http://testserver/api/v1/users/{self.user.username}"
        self.assertEqual(self.project.organization, self.user)

    def _patch(self, data, headers=None, viewset=ProjectViewSet):
        view = viewset.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, **{**self.extra, **(headers or {})}
        )
        return view(request, pk=self.project.pk)

    def _owner(self):
        self.project.refresh_from_db()
        return self.project.organization

    def test_transferring_a_project_is_challenged(self):
        response = self._patch({"owner": self.org_url})

        self.assert_challenged(response)
        self.assertEqual(self._owner(), self.user)

    def test_a_full_update_transferring_a_project_is_challenged(self):
        """A full update writes ``owner`` too, without the transfer command."""
        view = ProjectViewSet.as_view({"put": "update"})
        data = {"name": "demo", "owner": self.org_url, "public": False}
        request = self.factory.put("/", data=data, **self.extra)

        response = view(request, pk=self.project.pk)

        self.assert_challenged(response)
        self.assertEqual(self._owner(), self.user)

    def test_transferring_through_v2_is_challenged(self):
        response = self._patch({"owner": self.org_url}, viewset=ProjectViewSetV2)

        self.assert_challenged(response)
        self.assertEqual(self._owner(), self.user)

    def test_a_grant_lets_the_transfer_through(self):
        grant = self._grant()

        response = self._patch({"owner": self.org_url}, self._with_grant(grant))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._owner(), self.org_user)
        self.assert_spent(grant)

    def test_keeping_the_owner_is_not_challenged(self):
        self.assert_challenged(self._patch({"owner": self.org_url}))

        response = self._patch({"owner": self.user_url, "name": "renamed"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._owner(), self.user)
        self.assertEqual(self.project.name, "renamed")

    def test_an_invalid_transfer_keeps_the_grant(self):
        """Validation comes first, so a blank name does not spend it."""
        self.assert_challenged(self._patch({"owner": self.org_url}))
        grant = self._grant()

        response = self._patch(
            {"owner": self.org_url, "name": ""}, self._with_grant(grant)
        )

        self.assertEqual(response.status_code, 400)
        self.assert_unspent(grant)
        self.assertEqual(self._owner(), self.user)

    @gating_together(GATE_TRANSFER_PROJECT, GATE_PUBLISH_DATA)
    def test_a_transfer_that_also_publishes_is_refused_whole(self):
        grant = self._grant()

        response = self._patch(
            {"name": "renamed", "owner": self.org_url, "public": True},
            self._with_grant(grant),
        )

        self.assert_one_gated_change(
            response, [GATE_TRANSFER_PROJECT, GATE_PUBLISH_DATA]
        )
        self.assert_unspent(grant)
        self.assertEqual(self._owner(), self.user)
        self.assertEqual(self.project.name, "demo")
        self.assertFalse(self.project.shared)


@gating(GATE_FORM_REQUIRE_AUTH)
class TestFormRequireAuthGate(GateTestCase):
    """A form that stops requiring authentication can be downloaded and
    submitted to by anyone, so a stolen session must not be able to drop it."""

    audience = GATE_FORM_REQUIRE_AUTH

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self._set_require_auth(True)

    def _set_require_auth(self, value):
        XForm.objects.filter(pk=self.xform.pk).update(require_auth=value)
        self.assertEqual(self._require_auth(), value)

    def _require_auth(self):
        self.xform.refresh_from_db()
        return self.xform.require_auth

    def test_turning_off_require_auth_is_challenged(self):
        response = self._patch_form({"require_auth": False})

        self.assert_challenged(response)
        self.assertTrue(self._require_auth())

    def test_a_grant_lets_require_auth_off(self):
        grant = self._grant()

        response = self._patch_form({"require_auth": False}, self._with_grant(grant))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(self._require_auth())
        self.assert_spent(grant)

    def test_turning_on_require_auth_is_not_challenged(self):
        self.assert_challenged(self._patch_form({"require_auth": False}))
        self._set_require_auth(False)

        response = self._patch_form({"require_auth": True})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self._require_auth())

    def test_keeping_require_auth_on_is_not_challenged(self):
        self.assert_challenged(self._patch_form({"require_auth": False}))

        response = self._patch_form({"require_auth": True, "description": "renamed"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self._require_auth())
        self.assertEqual(self.xform.description, "renamed")

    def test_an_invalid_update_keeps_the_grant(self):
        """Validation comes first, so a malformed public key does not spend it."""
        self.assert_challenged(self._patch_form({"require_auth": False}))
        grant = self._grant()

        response = self._patch_form(
            {"require_auth": False, "public_key": "not-a-key"},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 400)
        self.assert_unspent(grant)
        self.assertTrue(self._require_auth())

    @gating_together(GATE_FORM_REQUIRE_AUTH, GATE_PUBLISH_DATA)
    def test_dropping_require_auth_while_publishing_is_refused_whole(self):
        grant = self._grant()

        response = self._patch_form(
            {"require_auth": False, "public_data": True}, self._with_grant(grant)
        )

        self.assert_one_gated_change(
            response, [GATE_FORM_REQUIRE_AUTH, GATE_PUBLISH_DATA]
        )
        self.assert_unspent(grant)
        self.assertTrue(self._require_auth())
        self.assertFalse(self.xform.shared_data)


@gating(GATE_DISABLE_FORM_ENCRYPTION)
class TestDisableFormEncryptionGate(GateTestCase):
    """Turning encryption off stores the next submissions readable, so a
    stolen session must not be able to do it."""

    audience = GATE_DISABLE_FORM_ENCRYPTION

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self._encrypt_xform(self.xform, self._create_kms_key(self.user))
        self.assertTrue(self._encrypted())
        self.assertTrue(self.xform.is_managed)
        self.assertEqual(self.xform.num_of_submissions, 0)

    def _encrypted(self):
        self.xform.refresh_from_db()
        return self.xform.encrypted

    def test_disabling_encryption_is_challenged(self):
        response = self._patch_form({"enable_kms_encryption": False})

        self.assert_challenged(response)
        self.assertTrue(self._encrypted())

    def test_a_grant_lets_encryption_off(self):
        grant = self._grant()

        response = self._patch_form(
            {"enable_kms_encryption": False}, self._with_grant(grant)
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(self._encrypted())
        self.assert_spent(grant)

    def test_enabling_encryption_is_not_challenged(self):
        self.assert_challenged(self._patch_form({"enable_kms_encryption": False}))

        response = self._patch_form({"enable_kms_encryption": True})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self._encrypted())

    def test_a_form_with_submissions_is_not_challenged(self):
        """Encryption stays on for a form with submissions, so the refusal
        that follows must not cost the grant."""
        self.assert_challenged(self._patch_form({"enable_kms_encryption": False}))
        XForm.objects.filter(pk=self.xform.pk).update(num_of_submissions=1)
        grant = self._grant()

        response = self._patch_form(
            {"enable_kms_encryption": False}, self._with_grant(grant)
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("already has submissions", str(response.data))
        self.assert_unspent(grant)
        self.assertTrue(self._encrypted())

    def test_an_invalid_update_keeps_the_grant(self):
        """Validation comes first, so a public key on a managed form does not
        spend it."""
        self.assert_challenged(self._patch_form({"enable_kms_encryption": False}))
        grant = self._grant()

        response = self._patch_form(
            {"enable_kms_encryption": False, "public_key": "not-a-key"},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 400)
        self.assert_unspent(grant)
        self.assertTrue(self._encrypted())

    @gating_together(GATE_DISABLE_FORM_ENCRYPTION, GATE_FORM_REQUIRE_AUTH)
    def test_disabling_encryption_and_require_auth_is_refused_whole(self):
        XForm.objects.filter(pk=self.xform.pk).update(require_auth=True)
        grant = self._grant()

        response = self._patch_form(
            {"enable_kms_encryption": False, "require_auth": False},
            self._with_grant(grant),
        )

        self.assert_one_gated_change(
            response, [GATE_DISABLE_FORM_ENCRYPTION, GATE_FORM_REQUIRE_AUTH]
        )
        self.assert_unspent(grant)
        self.assertTrue(self._encrypted())
        self.assertTrue(self.xform.require_auth)


@gating(GATE_PUBLISH_DATA)
class TestMoveFormIntoPublicProjectGate(GateTestCase):
    """A private form moved into a public project becomes public, data
    included, so a stolen session must not be able to move it there."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.private_project = self.project
        self.assertFalse(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.public_project = self._public_project("open")

    def _public_project(self, name, owner_url=None):
        extra = {"owner": owner_url} if owner_url else {}
        self._project_create({"name": name, **extra})
        Project.objects.filter(pk=self.project.pk).update(shared=True)
        self.project.refresh_from_db()
        self.assertTrue(self.project.shared)
        return self.project

    def _move(self, project, headers=None):
        view = ProjectViewSet.as_view({"post": "forms"})
        request = self.factory.post(
            "/",
            data={"formid": self.xform.pk},
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=project.pk)

    def _reload(self):
        self.xform.refresh_from_db()

    def test_moving_a_private_form_into_a_public_project_is_challenged(self):
        response = self._move(self.public_project)

        self.assert_challenged(response)
        self._reload()
        self.assertEqual(self.xform.project, self.private_project)
        self.assertFalse(self.xform.shared_data)

    def test_a_grant_lets_the_form_move(self):
        grant = self._grant()

        response = self._move(self.public_project, self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self._reload()
        self.assertEqual(self.xform.project, self.public_project)
        self.assertTrue(self.xform.shared_data)
        self.assert_spent(grant)

    def test_moving_into_a_private_project_is_not_challenged(self):
        self.assert_challenged(self._move(self.public_project))
        self._project_create({"name": "closed"})
        closed = self.project
        self.assertFalse(closed.shared)

        response = self._move(closed)

        self.assertEqual(response.status_code, 201, response.data)
        self._reload()
        self.assertEqual(self.xform.project, closed)
        self.assertFalse(self.xform.shared_data)

    def test_moving_a_public_form_is_not_challenged(self):
        self.assert_challenged(self._move(self.public_project))
        XForm.objects.filter(pk=self.xform.pk).update(shared=True, shared_data=True)

        response = self._move(self.public_project)

        self.assertEqual(response.status_code, 201, response.data)
        self._reload()
        self.assertEqual(self.xform.project, self.public_project)

    def test_an_invalid_move_keeps_the_grant(self):
        """The id_string check comes first, so a clash does not spend it."""
        self.assert_challenged(self._move(self.public_project))
        private_xform = self.xform
        self._org_create()
        org_url = f"http://testserver/api/v1/users/{self.organization.user.username}"
        org_project = self._public_project("org open", owner_url=org_url)
        self._publish_xls_form_to_project()
        self.assertEqual(self.xform.id_string, private_xform.id_string)
        self.xform = private_xform
        grant = self._grant()

        response = self._move(org_project, self._with_grant(grant))

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unspent(grant)
        self._reload()
        self.assertEqual(self.xform.project, self.private_project)
        self.assertFalse(self.xform.shared_data)


@gating(GATE_PUBLISH_DATA)
class TestOpenDataLinkGate(GateTestCase):
    """An open-data link reads a form's data without logging in, so a stolen
    session must not be able to open one."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assertFalse(OpenData.objects.exists())

    def _request(self, method, action, data, headers=None, **kwargs):
        view = OpenDataViewSet.as_view({method: action})
        request = getattr(self.factory, method)(
            "/",
            data=json.dumps(data),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, **kwargs)

    def _create(self, headers=None, **data):
        payload = {
            "object_id": self.xform.pk,
            "name": "tableau",
            "data_type": "xform",
            **data,
        }
        return self._request("post", "create", payload, headers)

    def _patch(self, open_data, data, headers=None):
        return self._request(
            "patch", "partial_update", data, headers, uuid=open_data.uuid
        )

    def _link(self, active=True):
        open_data, _created = get_or_create_opendata(self.xform)
        OpenData.objects.filter(pk=open_data.pk).update(active=active)
        open_data.refresh_from_db()
        self.assertEqual(open_data.active, active)
        return open_data

    def test_creating_a_link_is_challenged(self):
        response = self._create()

        self.assert_challenged(response)
        self.assertFalse(OpenData.objects.exists())

    def test_a_grant_lets_the_link_be_created(self):
        grant = self._grant()

        response = self._create(self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        open_data = OpenData.objects.get()
        self.assertTrue(open_data.active)
        self.assertEqual(response.data["uuid"], open_data.uuid)
        self.assert_spent(grant)

    def test_asking_for_an_existing_link_is_not_challenged(self):
        self.assert_challenged(self._create())
        open_data = self._link()

        response = self._create()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["uuid"], open_data.uuid)
        self.assertEqual(OpenData.objects.count(), 1)

    def test_an_invalid_link_keeps_the_grant(self):
        """Validation comes first, so an unsupported data type does not
        spend it."""
        self.assert_challenged(self._create())
        grant = self._grant()

        response = self._create(self._with_grant(grant), data_type="dataview")

        self.assertEqual(response.status_code, 400)
        self.assert_unspent(grant)
        self.assertFalse(OpenData.objects.exists())

    def test_reactivating_a_link_is_challenged(self):
        open_data = self._link(active=False)

        response = self._patch(open_data, {"active": True})

        self.assert_challenged(response)
        open_data.refresh_from_db()
        self.assertFalse(open_data.active)

    def test_a_grant_reactivates_the_link(self):
        open_data = self._link(active=False)
        grant = self._grant()

        response = self._patch(open_data, {"active": True}, self._with_grant(grant))

        self.assertEqual(response.status_code, 200, response.data)
        open_data.refresh_from_db()
        self.assertTrue(open_data.active)
        self.assert_spent(grant)

    def test_pointing_a_link_at_another_form_is_challenged(self):
        open_data = self._link()
        first_form = self.xform
        self._publish_xls_form_to_project(
            xlsform_path=os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "hxl_example",
                "hxl_example.xlsx",
            )
        )
        self.assertNotEqual(self.xform.pk, first_form.pk)

        response = self._patch(open_data, {"object_id": self.xform.pk})

        self.assert_challenged(response)
        open_data.refresh_from_db()
        self.assertEqual(open_data.object_id, first_form.pk)

    def test_deactivating_a_link_is_not_challenged(self):
        open_data = self._link(active=False)
        self.assert_challenged(self._patch(open_data, {"active": True}))
        OpenData.objects.filter(pk=open_data.pk).update(active=True)

        response = self._patch(open_data, {"active": False})

        self.assertEqual(response.status_code, 200, response.data)
        open_data.refresh_from_db()
        self.assertFalse(open_data.active)

    def test_renaming_an_active_link_is_not_challenged(self):
        open_data = self._link(active=False)
        self.assert_challenged(self._patch(open_data, {"active": True}))
        OpenData.objects.filter(pk=open_data.pk).update(active=True)

        response = self._patch(open_data, {"name": "renamed", "active": True})

        self.assertEqual(response.status_code, 200, response.data)
        open_data.refresh_from_db()
        self.assertEqual(open_data.name, "renamed")
        self.assertTrue(open_data.active)

    def test_an_invalid_reactivation_keeps_the_grant(self):
        """Validation comes first, so an unsupported data type does not
        spend it."""
        open_data = self._link(active=False)
        self.assert_challenged(self._patch(open_data, {"active": True}))
        grant = self._grant()

        response = self._patch(
            open_data,
            {"active": True, "data_type": "dataview"},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 400)
        self.assert_unspent(grant)
        open_data.refresh_from_db()
        self.assertFalse(open_data.active)
