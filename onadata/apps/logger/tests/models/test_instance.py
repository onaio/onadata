import os
import pytz
from datetime import datetime
from datetime import timedelta

from django.http.request import HttpRequest
from django.utils.timezone import utc
from django_digest.test import DigestAuth
from mock import patch, Mock

from onadata.apps.logger.models import XForm, Instance, SubmissionReview
from onadata.apps.logger.models.instance import (
    get_id_string_from_xml_str,
    numeric_checker,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.parsed_instance import (
    ParsedInstance,
    query_data,
    query_fields_data,
)
from onadata.libs.serializers.submission_review_serializer import (
    SubmissionReviewSerializer,
)
from onadata.libs.utils.common_tags import (
    MONGO_STRFTIME,
    SUBMITTED_BY,
)


class TestInstance(TestBase):
    def setUp(self):
        super(self.__class__, self).setUp()

    def test_stores_json(self):
        self._publish_transportation_form_and_submit_instance()
        instances = Instance.objects.all()
        xform_id_string = XForm.objects.all()[0].id_string

        for instance in instances:
            self.assertNotEqual(instance.json, {})
            self.assertEqual(instance.json.get("_id"), instance.pk)
            self.assertEqual(
                instance.json.get("_date_modified"), instance.date_modified.isoformat()
            )
            self.assertEqual(
                instance.json.get("_submission_time"), instance.date_created.isoformat()
            )
            self.assertEqual(instance.json.get("_xform_id_string"), xform_id_string)

    def test_updates_json_date_modifed_on_save(self):
        """_date_modified in json is updated on save"""
        old_mocked_now = datetime(2023, 9, 21, 8, 27, 0, tzinfo=pytz.utc)

        with patch("django.utils.timezone.now", Mock(return_value=old_mocked_now)):
            self._publish_transportation_form_and_submit_instance()

        instance = Instance.objects.first()
        self.assertEqual(instance.date_modified, old_mocked_now)
        self.assertEqual(
            instance.json.get("_date_modified"), old_mocked_now.isoformat()
        )

        # After saving the date_modified in json should update
        mocked_now = datetime(2023, 9, 21, 9, 3, 0, tzinfo=pytz.utc)

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            instance.save()

        instance.refresh_from_db()
        self.assertEqual(instance.date_modified, mocked_now)
        self.assertEqual(instance.json.get("_date_modified"), mocked_now.isoformat())
        # date_created, _submission_time is not altered
        self.assertEqual(instance.date_created, old_mocked_now)
        self.assertEqual(
            instance.json.get("_submission_time"), old_mocked_now.isoformat()
        )

    @patch("django.utils.timezone.now")
    def test_json_stores_user_attribute(self, mock_time):
        mock_time.return_value = datetime.utcnow().replace(tzinfo=utc)
        self._publish_transportation_form()

        # make account require phone auth
        self.user.profile.require_auth = True
        self.user.profile.save()

        # submit instance with a request user
        path = os.path.join(
            self.this_directory,
            "fixtures",
            "transportation",
            "instances",
            self.surveys[0],
            self.surveys[0] + ".xml",
        )

        auth = DigestAuth(self.login_username, self.login_password)
        self._make_submission(path, auth=auth)

        instances = Instance.objects.filter(xform_id=self.xform).all()
        self.assertTrue(len(instances) > 0)

        for instance in instances:
            self.assertEqual(instance.json[SUBMITTED_BY], "bob")
            # check that the parsed instance's to_dict_for_mongo also contains
            # the _user key, which is what's used by the JSON REST service
            pi = ParsedInstance.objects.get(instance=instance)
            self.assertEqual(pi.to_dict_for_mongo()[SUBMITTED_BY], "bob")

    def test_set_instances_with_geopoints_on_submission_false(self):
        self._publish_transportation_form()

        self.assertFalse(self.xform.instances_with_geopoints)

        self._make_submissions()
        xform = XForm.objects.get(pk=self.xform.pk)

        self.assertFalse(xform.instances_with_geopoints)

    def test_instances_with_geopoints_in_repeats(self):
        xls_path = self._fixture_path("gps", "gps_in_repeats.xlsx")
        self._publish_xls_file_and_set_xform(xls_path)

        self.assertFalse(self.xform.instances_with_geopoints)

        instance_path = self._fixture_path("gps", "gps_in_repeats_submission.xml")
        self._make_submission(instance_path)
        xform = XForm.objects.get(pk=self.xform.pk)

        self.assertTrue(xform.instances_with_geopoints)

    def test_set_instances_with_geopoints_on_submission_true(self):
        xls_path = self._fixture_path("gps", "gps.xlsx")
        self._publish_xls_file_and_set_xform(xls_path)

        self.assertFalse(self.xform.instances_with_geopoints)

        self._make_submissions_gps()
        xform = XForm.objects.get(pk=self.xform.pk)

        self.assertTrue(xform.instances_with_geopoints)

    @patch("onadata.apps.logger.models.instance.get_values_matching_key")
    def test_instances_with_malformed_geopoints_dont_trigger_value_error(
        self, mock_get_values_matching_key
    ):
        mock_get_values_matching_key.return_value = "40.81101715564728"
        xls_path = self._fixture_path("gps", "gps.xlsx")
        self._publish_xls_file_and_set_xform(xls_path)

        self.assertFalse(self.xform.instances_with_geopoints)

        path = self._fixture_path("gps", "instances", "gps_1980-01-23_20-52-08.xml")
        self._make_submission(path)
        xform = XForm.objects.get(pk=self.xform.pk)
        self.assertFalse(xform.instances_with_geopoints)

    def test_get_id_string_from_xml_str(self):
        submission = """<?xml version="1.0" encoding="UTF-8" ?>
        <submission xmlns:orx="http://openrosa.org/xforms">
            <data>
                <id_string id="id_string">
                    <element>data</element>
                    <data>random</data>
                </id_string>
            </data>
        </submission>
        """
        id_string = get_id_string_from_xml_str(submission)
        self.assertEqual(id_string, "id_string")

    def test_query_data_sort(self):
        self._publish_transportation_form()
        self._make_submissions()
        latest = Instance.objects.filter(xform=self.xform).latest("pk").pk
        oldest = Instance.objects.filter(xform=self.xform).first().pk

        data = [i.get("_id") for i in query_data(self.xform, sort="-_id")]
        self.assertEqual(data[0], latest)
        self.assertEqual(data[len(data) - 1], oldest)

        # sort with a json field
        data = [i.get("_id") for i in query_data(self.xform, sort='{"_id": "-1"}')]
        self.assertEqual(data[0], latest)
        self.assertEqual(data[len(data) - 1], oldest)

        # sort with a json field
        data = [i.get("_id") for i in query_data(self.xform, sort='{"_id": -1}')]
        self.assertEqual(data[0], latest)
        self.assertEqual(data[len(data) - 1], oldest)

    def test_query_filter_by_integer(self):
        self._publish_transportation_form()
        self._make_submissions()
        oldest = Instance.objects.filter(xform=self.xform).first().pk

        data = [
            i.get("_id")
            for i in query_data(self.xform, query='[{"_id": %s}]' % (oldest))
        ]
        self.assertEqual(len(data), 1)
        self.assertEqual(data, [oldest])

        # with fields
        data = [
            i.get("_id")
            for i in query_fields_data(
                self.xform, query='{"_id": %s}' % (oldest), fields='["_id"]'
            )
        ]
        self.assertEqual(len(data), 1)
        self.assertEqual(data, [oldest])

        # mongo $gt
        data = [
            i.get("_id")
            for i in query_fields_data(
                self.xform, query='{"_id": {"$gt": %s}}' % (oldest), fields='["_id"]'
            )
        ]
        self.assertEqual(self.xform.instances.count(), 4)
        self.assertEqual(len(data), 3)

    @patch("onadata.apps.logger.models.instance.submission_time")
    def test_query_filter_by_datetime_field(self, mock_time):
        self._publish_transportation_form()
        now = datetime(2014, 1, 1, tzinfo=utc)
        times = [
            now,
            now + timedelta(seconds=1),
            now + timedelta(seconds=2),
            now + timedelta(seconds=3),
        ]
        mock_time.side_effect = times
        self._make_submissions()

        atime = None

        for i in self.xform.instances.all().order_by("-pk"):
            i.date_created = times.pop()
            i.save()
            if atime is None:
                atime = i.date_created.strftime(MONGO_STRFTIME)

        # mongo $gt
        data = [
            i.get("_submission_time")
            for i in query_fields_data(
                self.xform,
                query='{"_submission_time": {"$lt": "%s"}}' % (atime),
                fields='["_submission_time"]',
            )
        ]
        self.assertEqual(self.xform.instances.count(), 4)
        self.assertEqual(len(data), 3)
        self.assertNotIn(atime, data)

    def test_instance_json_updated_on_review(self):
        """
        Test:
            -no review comment or status on instance json
                before submission review
            -instance json review fields update on review save
            -instance review methods
        """
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        self.assertNotIn("_review_status", instance.json.keys())
        self.assertNotIn("_review_comment", instance.json.keys())
        self.assertFalse(instance.has_a_review)

        data = {"instance": instance.id, "status": SubmissionReview.APPROVED}
        request = HttpRequest()
        request.user = self.user

        serializer_instance = SubmissionReviewSerializer(
            data=data, context={"request": request}
        )
        serializer_instance.is_valid()
        serializer_instance.save()
        instance.refresh_from_db()
        instance_review = instance.get_latest_review()

        self.assertNotIn("_review_comment", instance.json.keys())
        self.assertIn("_review_status", instance.json.keys())
        self.assertIn("_review_date", instance.json.keys())
        self.assertEqual(SubmissionReview.APPROVED, instance.json["_review_status"])
        self.assertEqual(SubmissionReview.APPROVED, instance_review.status)
        comment = instance_review.get_note_text()
        self.assertEqual(None, comment)
        self.assertTrue(instance.has_a_review)

        data = {
            "instance": instance.id,
            "note": "Hey There",
            "status": SubmissionReview.APPROVED,
        }

        serializer_instance = SubmissionReviewSerializer(
            data=data, context={"request": request}
        )
        serializer_instance.is_valid()
        serializer_instance.save()
        instance.refresh_from_db()
        instance_review = instance.get_latest_review()

        self.assertIn("_review_comment", instance.json.keys())
        self.assertIn("_review_status", instance.json.keys())
        self.assertIn("_review_date", instance.json.keys())
        self.assertEqual(SubmissionReview.APPROVED, instance.json["_review_status"])
        self.assertEqual(SubmissionReview.APPROVED, instance_review.status)
        comment = instance_review.get_note_text()
        self.assertEqual("Hey There", comment)
        self.assertTrue(instance.has_a_review)

    def test_retrieve_non_existent_submission_review(self):
        """
        Test fetch submission review for instance when
        a submission review was never created for the submission
        """

        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        self.assertNotIn("_review_status", instance.json.keys())
        self.assertNotIn("_review_comment", instance.json.keys())
        self.assertFalse(instance.has_a_review)

        # Update instance has_a_review field
        instance.has_a_review = True
        instance.save()
        instance.refresh_from_db()

        # Test that we return None for
        # instances when SubmissionReview.DoesNotExist
        self.assertIsNone(instance.get_latest_review())

        # Test instance json is not updated
        self.assertNotIn("_review_comment", instance.json.keys())
        self.assertNotIn("_review_status", instance.json.keys())
        self.assertNotIn("_review_date", instance.json.keys())

    def test_numeric_checker_with_negative_integer_values(self):
        # Evaluate negative integer values
        string_value = "-16"
        result = numeric_checker(string_value)
        self.assertEqual(result, -16)

        # Evaluate un-signed integer values
        string_value = "16"
        result = numeric_checker(string_value)
        self.assertEqual(result, 16)

        # Evaluate float values
        string_value = "36.23"
        result = numeric_checker(string_value)
        self.assertEqual(result, 36.23)

        # Evaluate nan values
        string_value = float("NaN")
        result = numeric_checker(string_value)
        self.assertEqual(result, 0)

        # Evaluate non-string values
        string_value = "Hello World"
        result = numeric_checker(string_value)
        self.assertEqual(result, "Hello World")
