"""Tests that reads of a merged dataset leave out its deleted source forms."""

import json
from datetime import timedelta

from django.utils import timezone

from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.v2.tableau_viewset import TableauViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import DataView, XForm
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.serializers.merged_xform_serializer import MergedXFormSerializer
from onadata.libs.utils.cache_tools import XFORM_COUNT, safe_cache_delete


def _fruits(response):
    rows = json.loads("".join(i.decode("utf-8") for i in response.streaming_content))
    return sorted(row["fruit"] for row in rows)


class MergedXFormSourceFormsTestCase(TestBase):
    """Form a has an orange submission and form b, the newer one, a mango"""

    def setUp(self):
        super().setUp()
        self.merged_xform = self._create_merged_dataset(make_submissions=True)
        # The submission count is cached by form pk, and the cache outlives the
        # test database
        self._clear_count_cache()
        self.addCleanup(self._clear_count_cache)
        self.xform = XForm.objects.get(pk=self.merged_xform.pk)
        self.form_a = self.merged_xform.xforms.get(id_string="a")
        self.form_b = self.merged_xform.xforms.get(id_string="b")
        self.form_a.last_submission_time = timezone.now() - timedelta(days=1)
        self.form_a.save(update_fields=["last_submission_time"])
        self.form_b.last_submission_time = timezone.now()
        self.form_b.save(update_fields=["last_submission_time"])
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}

    def _clear_count_cache(self):
        safe_cache_delete(f"{XFORM_COUNT}{self.merged_xform.pk}")

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

    def _create_data_view(self):
        return DataView.objects.create(
            name="fruits",
            xform=self.xform,
            project=self.project,
            columns=["fruit"],
            query=[],
        )

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
        self.assertEqual(self._get_data(OpenDataViewSet, count=True).data["count"], 1)

    def test_tableau_leaves_out_deleted_source_form(self):
        self.assertEqual(_fruits(self._get_data(TableauViewSet)), ["mango", "orange"])

        self._delete_form_b()

        self.assertEqual(_fruits(self._get_data(TableauViewSet)), ["orange"])
        self.assertEqual(
            _fruits(self._get_data(TableauViewSet, page=1, page_size=10)), ["orange"]
        )
        self.assertEqual(self._get_data(TableauViewSet, count=True).data["count"], 1)

    def test_filtered_dataset_leaves_out_deleted_source_form(self):
        data_view = self._create_data_view()
        self.assertEqual(
            sorted(row["fruit"] for row in DataView.query_data(data_view)),
            ["mango", "orange"],
        )

        self._delete_form_b()

        self.assertEqual(
            [row["fruit"] for row in DataView.query_data(data_view)], ["orange"]
        )
        self.assertEqual(DataView.query_data(data_view, count=True), [{"count": 1}])

    def test_data_is_empty_when_all_source_forms_are_deleted(self):
        data_view = self._create_data_view()

        self._delete_all_source_forms()

        self.assertEqual(_fruits(self._get_data(OpenDataViewSet)), [])
        self.assertEqual(_fruits(self._get_data(TableauViewSet)), [])
        self.assertEqual(
            _fruits(self._get_data(TableauViewSet, page=1, page_size=10)), []
        )
        self.assertEqual(self._get_data(TableauViewSet, count=True).data["count"], 0)
        self.assertEqual(DataView.query_data(data_view), [])
        self.assertEqual(DataView.query_data(data_view, count=True), [{"count": 0}])

    def test_submission_count_leaves_out_deleted_source_form(self):
        self.assertEqual(self.xform.submission_count(force_update=True), 2)

        self._delete_form_b()

        self.assertEqual(self.xform.submission_count(force_update=True), 1)

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

    def test_merged_serializer_last_submission_time_without_annotation(self):
        serializer = MergedXFormSerializer()
        self.assertEqual(
            serializer.get_last_submission_time(self.merged_xform),
            self.form_b.last_submission_time.isoformat(),
        )

        self._delete_form_b()

        self.assertEqual(
            serializer.get_last_submission_time(self.merged_xform),
            self.form_a.last_submission_time.isoformat(),
        )
