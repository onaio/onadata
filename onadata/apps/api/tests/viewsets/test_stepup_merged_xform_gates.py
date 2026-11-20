# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on creating a merged dataset, which publishes its
source forms' data in a public project and hands it to the account that owns
the project.
"""

from onadata.apps.api.tests.viewsets.test_merged_xform_viewset import MD
from onadata.apps.api.tests.viewsets.test_stepup_form_and_transfer_gates import (
    GateTestCase,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import gating
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.logger.models import MergedXForm, Project
from onadata.libs.stepup.policy import GATE_PUBLISH_DATA, GATE_TRANSFER_PROJECT
from onadata.libs.utils.user_auth import get_user_default_project


class MergedXFormGateTestCase(GateTestCase):
    """Two private forms in the user's own project, ready to merge."""

    def setUp(self):
        super().setUp()
        # pylint: disable=attribute-defined-outside-init
        self.project = self.own_project = get_user_default_project(self.user)
        self.xform_a = self._publish_markdown(MD, self.user, id_string="a")
        self.xform_b = self._publish_markdown(MD, self.user, id_string="b")
        for xform in (self.xform_a, self.xform_b):
            self.assertEqual(xform.user, self.user)
            self.assertFalse(xform.shared_data)

    def _merge(self, project, headers=None):
        view = MergedXFormViewSet.as_view({"post": "create"})
        data = {
            "xforms": [
                f"http://testserver/api/v1/forms/{xform.pk}"
                for xform in (self.xform_a, self.xform_b)
            ],
            "name": "Merged Dataset",
            "project": f"http://testserver/api/v1/projects/{project.pk}",
        }
        request = self.factory.post("/", data=data, **{**self.extra, **(headers or {})})
        return view(request)

    @staticmethod
    def _set_public(project, shared):
        Project.objects.filter(pk=project.pk).update(shared=shared)
        project.refresh_from_db()


@gating(GATE_PUBLISH_DATA)
class TestMergeIntoPublicProjectGate(MergedXFormGateTestCase):
    """A merged dataset in a public project is public, so merging private
    forms there publishes their data."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        self._set_public(self.own_project, True)

    def test_merging_private_forms_into_a_public_project_is_challenged(self):
        """The 401 names the audience and no merged dataset is made."""
        response = self._merge(self.own_project)

        self.assert_challenged(response)
        self.assertFalse(MergedXForm.objects.exists())

    def test_a_grant_lets_the_merge_through(self):
        """With a grant the merged dataset is made in the public project."""
        grant = self._grant()

        response = self._merge(self.own_project, self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            MergedXForm.objects.get(pk=response.data["id"]).project,
            self.own_project,
        )
        self.assert_spent(grant)

    def test_merging_into_a_private_project_is_not_challenged(self):
        """A private project publishes nothing."""
        self.assert_challenged(self._merge(self.own_project))
        self._set_public(self.own_project, False)

        response = self._merge(self.own_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(MergedXForm.objects.filter(pk=response.data["id"]).exists())

    def test_an_invalid_merge_keeps_the_grant(self):
        """Validation comes first, so a single form does not spend it."""
        self.assert_challenged(self._merge(self.own_project))
        grant = self._grant()
        self.xform_b = self.xform_a

        response = self._merge(self.own_project, self._with_grant(grant))

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unspent(grant)
        self.assertFalse(MergedXForm.objects.exists())


@gating(GATE_TRANSFER_PROJECT)
class TestMergeIntoAnotherAccountGate(MergedXFormGateTestCase):
    """A merged dataset belongs to its project's account, whose admins read
    the source forms' data through it, so merging into another account's
    project hands that data over."""

    audience = GATE_TRANSFER_PROJECT

    def setUp(self):
        super().setUp()
        self._org_create()
        org_url = f"http://testserver/api/v1/users/{self.organization.user.username}"
        self._project_create({"name": "org project", "owner": org_url})
        self.org_project = self.project
        self.assertEqual(self.org_project.organization, self.organization.user)
        self.assertFalse(self.org_project.shared)

    def test_merging_into_another_accounts_project_is_challenged(self):
        """The 401 names the audience and no merged dataset is made."""
        response = self._merge(self.org_project)

        self.assert_challenged(response)
        self.assertFalse(MergedXForm.objects.exists())

    def test_a_grant_lets_the_merge_through(self):
        """With a grant the merged dataset is made in the other account."""
        grant = self._grant()

        response = self._merge(self.org_project, self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            MergedXForm.objects.get(pk=response.data["id"]).project,
            self.org_project,
        )
        self.assert_spent(grant)

    def test_merging_within_the_account_is_not_challenged(self):
        """The forms' own account keeps their data."""
        self.assert_challenged(self._merge(self.org_project))

        response = self._merge(self.own_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            MergedXForm.objects.get(pk=response.data["id"]).project,
            self.own_project,
        )

    @gating(GATE_TRANSFER_PROJECT, GATE_PUBLISH_DATA)
    def test_a_merge_that_also_publishes_is_refused_whole(self):
        """Into another account's public project is two gated changes."""
        self._set_public(self.org_project, True)
        grant = self._grant()

        response = self._merge(self.org_project, self._with_grant(grant))

        self.assert_one_gated_change(
            response, [GATE_TRANSFER_PROJECT, GATE_PUBLISH_DATA]
        )
        self.assert_unspent(grant)
        self.assertFalse(MergedXForm.objects.exists())
