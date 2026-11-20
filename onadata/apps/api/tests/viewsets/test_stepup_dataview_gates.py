# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on dataviews, which anyone can read once they sit
in a public project.
"""

import os

from django.conf import settings

from onadata.apps.api.tests.viewsets.test_stepup_form_and_transfer_gates import (
    GateTestCase,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import gating
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.logger.models import DataView, Project, XForm
from onadata.libs.permissions import ManagerRole
from onadata.libs.stepup.policy import GATE_PUBLISH_DATA

COLUMNS = '["name", "age"]'


@gating(GATE_PUBLISH_DATA)
class TestPublishDataViewGate(GateTestCase):
    """A dataview in a public project shows its source form's rows to anyone,
    so a stolen session must not be able to put one there."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.private_project = self.project
        self.public_project = self._managed_project("open", shared=True)
        self.assertFalse(self.private_project.shared)
        self.assertFalse(self.xform.shared_data)

    def _managed_project(self, name, shared):
        project = Project.objects.create(
            name=name,
            organization=self.user,
            created_by=self.user,
            metadata={},
            shared=shared,
        )
        ManagerRole.add(self.user, project)
        return project

    def _dataview(self, project):
        return DataView.objects.create(
            name="existing",
            xform=self.xform,
            project=project,
            columns=["name"],
        )

    @staticmethod
    def _url(kind, pk):
        return f"http://testserver/api/v1/{kind}/{pk}"

    def _create(self, project, headers=None):
        view = DataViewViewSet.as_view({"post": "create"})
        data = {
            "name": "My DataView",
            "xform": self._url("forms", self.xform.pk),
            "project": self._url("projects", project.pk),
            "columns": COLUMNS,
            "query": "[]",
        }
        request = self.factory.post("/", data=data, **{**self.extra, **(headers or {})})
        return view(request)

    def _patch(self, dataview, data, headers=None):
        view = DataViewViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, **{**self.extra, **(headers or {})}
        )
        return view(request, pk=dataview.pk)

    def test_creating_one_in_a_public_project_is_challenged(self):
        """The 401 names the audience and no dataview is made."""
        response = self._create(self.public_project)

        self.assert_challenged(response)
        self.assertFalse(DataView.objects.exists())

    def test_a_grant_lets_the_dataview_be_created(self):
        """With a grant the dataview is made in the public project."""
        grant = self._grant()

        response = self._create(self.public_project, self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(DataView.objects.get().project, self.public_project)
        self.assert_spent(grant)

    def test_creating_one_in_a_private_project_is_not_challenged(self):
        """A private project publishes nothing."""
        self.assert_challenged(self._create(self.public_project))

        response = self._create(self.private_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(DataView.objects.get().project, self.private_project)

    def test_one_over_public_data_is_not_challenged(self):
        """Data that is already public is not published again."""
        self.assert_challenged(self._create(self.public_project))
        XForm.objects.filter(pk=self.xform.pk).update(shared=True, shared_data=True)

        response = self._create(self.public_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(DataView.objects.get().project, self.public_project)

    def test_an_invalid_dataview_keeps_the_grant(self):
        """Validation comes first, so a missing name does not spend it."""
        self.assert_challenged(self._create(self.public_project))
        grant = self._grant()
        view = DataViewViewSet.as_view({"post": "create"})
        data = {
            "xform": self._url("forms", self.xform.pk),
            "project": self._url("projects", self.public_project.pk),
            "columns": COLUMNS,
        }
        request = self.factory.post(
            "/", data=data, **{**self.extra, **self._with_grant(grant)}
        )

        response = view(request)

        self.assertEqual(response.status_code, 400, response.data)
        self.assert_unspent(grant)
        self.assertFalse(DataView.objects.exists())

    def test_moving_one_into_a_public_project_is_challenged(self):
        """The 401 names the audience and the dataview stays put."""
        dataview = self._dataview(self.private_project)

        response = self._patch(
            dataview, {"project": self._url("projects", self.public_project.pk)}
        )

        self.assert_challenged(response)
        dataview.refresh_from_db()
        self.assertEqual(dataview.project, self.private_project)

    def test_a_grant_lets_the_dataview_move(self):
        """With a grant the dataview moves into the public project."""
        dataview = self._dataview(self.private_project)
        grant = self._grant()

        response = self._patch(
            dataview,
            {"project": self._url("projects", self.public_project.pk)},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 200, response.data)
        dataview.refresh_from_db()
        self.assertEqual(dataview.project, self.public_project)
        self.assert_spent(grant)

    def test_showing_more_columns_in_a_public_project_is_challenged(self):
        """Widening a public dataview publishes the added columns."""
        dataview = self._dataview(self.public_project)

        response = self._patch(dataview, {"columns": COLUMNS})

        self.assert_challenged(response)
        dataview.refresh_from_db()
        self.assertEqual(dataview.columns, ["name"])

    def test_renaming_one_in_a_public_project_is_not_challenged(self):
        """A new name shows nothing new."""
        dataview = self._dataview(self.public_project)
        self.assert_challenged(self._patch(dataview, {"columns": COLUMNS}))

        response = self._patch(dataview, {"name": "renamed"})

        self.assertEqual(response.status_code, 200, response.data)
        dataview.refresh_from_db()
        self.assertEqual(dataview.name, "renamed")
        self.assertEqual(dataview.columns, ["name"])
