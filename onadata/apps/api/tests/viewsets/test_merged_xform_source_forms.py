"""Tests that reads of a merged dataset leave out its deleted source forms."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.v2.tableau_viewset import TableauViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import DataView, Project, XForm
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.cache_tools import (
    DATAVIEW_COUNT,
    DATAVIEW_LAST_SUBMISSION_TIME,
    XFORM_COUNT,
    safe_cache_delete,
    safe_cache_get,
)


def _fruits(response):
    rows = json.loads("".join(i.decode("utf-8") for i in response.streaming_content))
    return sorted(row["fruit"] for row in rows)


class MergedXFormSourceFormsTestCase(TestBase):
    """Form a has an orange submission and form b, the newer one, a mango"""

    def setUp(self):
        super().setUp()
        self.merged_xform = self._create_merged_dataset(make_submissions=True)
        # Counts are cached by form pk, and the cache outlives the test database
        self._clear_count_caches()
        self.addCleanup(self._clear_count_caches)
        self.xform = XForm.objects.get(pk=self.merged_xform.pk)
        self.form_a = self.merged_xform.xforms.get(id_string="a")
        self.form_b = self.merged_xform.xforms.get(id_string="b")
        self.form_a.last_submission_time = timezone.now() - timedelta(days=1)
        self.form_a.save(update_fields=["last_submission_time"])
        self.form_b.last_submission_time = timezone.now()
        self.form_b.save(update_fields=["last_submission_time"])
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}

    def _clear_count_caches(self):
        for key in (XFORM_COUNT, DATAVIEW_COUNT, DATAVIEW_LAST_SUBMISSION_TIME):
            safe_cache_delete(f"{key}{self.merged_xform.pk}")

    def _delete_form_b(self):
        """Deleting either source form deletes the merged dataset, and restoring
        form a brings it back while form b stays deleted"""
        self.form_a.soft_delete(self.user)
        self.form_b.soft_delete(self.user)
        self.form_a.refresh_from_db()
        self.form_a.restore()
        self.merged_xform.refresh_from_db()
        self.xform.refresh_from_db()
        self.assertIsNone(self.merged_xform.deleted_at)
        self.assertEqual(
            list(self.merged_xform.xforms.filter(deleted_at__isnull=True)),
            [self.form_a],
        )

    def _delete_all_source_forms(self):
        """Restoring the merged dataset itself leaves every source form deleted"""
        self.form_a.soft_delete(self.user)
        self.form_b.soft_delete(self.user)
        self.merged_xform.refresh_from_db()
        self.merged_xform.restore()
        self.merged_xform.refresh_from_db()
        self.xform.refresh_from_db()
        self.assertIsNone(self.merged_xform.deleted_at)
        self.assertEqual(self.merged_xform.xforms.count(), 2)
        self.assertFalse(self.merged_xform.xforms.filter(deleted_at=None).exists())

    def _get_data(self, viewset, **params):
        uuid = get_or_create_opendata(self.xform)[0].uuid
        request = self.factory.get("/", data=params, **self.extra)
        response = viewset.as_view({"get": "data"})(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        return response

    def _retrieve_data_view(self, data_view):
        request = self.factory.get("/", **self.extra)
        response = DataViewViewSet.as_view({"get": "retrieve"})(
            request, pk=data_view.pk
        )
        self.assertEqual(response.status_code, 200)
        return response.data

    def _retrieve_form(self):
        request = self.factory.get("/", **self.extra)
        response = XFormViewSet.as_view({"get": "retrieve"})(
            request, pk=self.merged_xform.pk
        )
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_open_data_leaves_out_deleted_source_form(self):
        self.assertEqual(_fruits(self._get_data(OpenDataViewSet)), ["mango", "orange"])

        self._delete_form_b()

        self.assertEqual(_fruits(self._get_data(OpenDataViewSet)), ["orange"])

    def test_tableau_leaves_out_deleted_source_form(self):
        self.assertEqual(_fruits(self._get_data(TableauViewSet)), ["mango", "orange"])

        self._delete_form_b()

        self.assertEqual(_fruits(self._get_data(TableauViewSet)), ["orange"])
        # The count comes from a separate query
        self.assertEqual(self._get_data(TableauViewSet, count=True).data["count"], 1)

    def test_filtered_dataset_follows_source_form_changes(self):
        data_view = DataView.objects.create(
            name="fruits",
            xform=self.xform,
            project=self.project,
            columns=["fruit"],
            query=[],
        )
        self._delete_form_b()
        time_key = f"{DATAVIEW_LAST_SUBMISSION_TIME}{self.merged_xform.pk}"

        self.assertEqual(self._retrieve_data_view(data_view)["count"], 1)
        self.assertIsNotNone(safe_cache_get(time_key))

        self.form_b.refresh_from_db()
        self.form_b.restore()

        self.assertIsNone(safe_cache_get(time_key))
        self.assertEqual(self._retrieve_data_view(data_view)["count"], 2)

    def test_stored_count_follows_source_form_changes(self):
        self.assertEqual(self.xform.submission_count(force_update=True), 2)

        self._delete_form_b()

        self.assertEqual(self.merged_xform.num_of_submissions, 1)

        self.form_b.refresh_from_db()
        self.form_b.restore()

        self.merged_xform.refresh_from_db()
        self.assertEqual(self.merged_xform.num_of_submissions, 2)

    @patch("onadata.apps.logger.models.xform.clear_project_cache")
    def test_source_form_change_clears_merged_dataset_project_cache(self, clear_cache):
        """The merged dataset can be in a different project from its source forms"""
        self._delete_form_b()
        other_project = Project.objects.create(
            name="other", organization=self.user, created_by=self.user
        )
        XForm.objects.filter(pk=self.merged_xform.pk).update(project=other_project)

        self.form_b.refresh_from_db()
        self.form_b.restore()

        clear_cache.assert_any_call(other_project.pk)

    def test_tableau_is_empty_when_all_source_forms_are_deleted(self):
        self.assertEqual(_fruits(self._get_data(TableauViewSet)), ["mango", "orange"])

        self._delete_all_source_forms()

        self.assertEqual(_fruits(self._get_data(TableauViewSet)), [])

    def test_form_details_report_zero_when_all_source_forms_are_deleted(self):
        self.assertEqual(self._retrieve_form()["num_of_submissions"], 2)

        self._delete_all_source_forms()

        self.assertEqual(self._retrieve_form()["num_of_submissions"], 0)

    def test_form_details_leave_out_deleted_source_form(self):
        details = self._retrieve_form()
        self.assertEqual(details["num_of_submissions"], 2)
        self.assertEqual(
            details["last_submission_time"],
            self.form_b.last_submission_time.isoformat(),
        )

        self._delete_form_b()

        details = self._retrieve_form()
        self.assertEqual(details["num_of_submissions"], 1)
        self.assertEqual(
            details["last_submission_time"],
            self.form_a.last_submission_time.isoformat(),
        )

        # The merged dataset is already active, so only the source form changes
        self.form_b.refresh_from_db()
        self.form_b.restore()

        details = self._retrieve_form()
        self.assertEqual(details["num_of_submissions"], 2)
        self.assertEqual(
            details["last_submission_time"],
            self.form_b.last_submission_time.isoformat(),
        )
