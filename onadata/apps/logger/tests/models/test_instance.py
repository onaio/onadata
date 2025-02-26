# -*- coding: utf-8 -*-
"""
Test Instance model.
"""

import json
import os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.contrib.contenttypes.models import ContentType
from django.http.request import HttpRequest
from django.test import override_settings

from django_digest.test import DigestAuth

from onadata.apps.logger.models import (Entity, EntityList, Instance,
                                        RegistrationForm, SubmissionReview,
                                        XForm)
from onadata.apps.logger.models.instance import (get_id_string_from_xml_str,
                                                 numeric_checker)
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.parsed_instance import (ParsedInstance,
                                                        query_data,
                                                        query_fields_data)
from onadata.libs.serializers.submission_review_serializer import \
    SubmissionReviewSerializer
from onadata.libs.utils.common_tags import MONGO_STRFTIME, SUBMITTED_BY
from onadata.libs.utils.user_auth import get_user_default_project


class TestInstance(TestBase):
    def setUp(self):
        super(self.__class__, self).setUp()

    def test_stores_json(self):
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()

        self.assertEqual(
            instance.json,
            {
                "_id": instance.pk,
                "_tags": [],
                "_uuid": "5b2cc313-fc09-437e-8149-fcd32f695d41",
                "_notes": [],
                "image1": "1335783522563.jpg",
                "_edited": False,
                "_status": "submitted_via_web",
                "_version": "2014111",
                "_duration": "",
                "_xform_id": instance.xform.pk,
                "_attachments": [],
                "_geolocation": [None, None],
                "_media_count": 0,
                "_total_media": 1,
                "_submitted_by": "bob",
                "_date_modified": instance.date_modified.isoformat(),
                "meta/instanceID": "uuid:5b2cc313-fc09-437e-8149-fcd32f695d41",
                "_submission_time": instance.date_created.isoformat(),
                "_xform_id_string": "transportation_2011_07_25",
                "_bamboo_dataset_id": "",
                "_media_all_received": False,
                "transport/available_transportation_types_to_referral_facility": "none",
            },
        )

    def test_updates_json_date_modified_on_save(self):
        """_date_modified in `json` field is updated on save"""
        old_mocked_now = datetime(2023, 9, 21, 8, 27, 0, tzinfo=timezone.utc)

        with patch("django.utils.timezone.now", Mock(return_value=old_mocked_now)):
            self._publish_transportation_form_and_submit_instance()

        instance = Instance.objects.first()
        self.assertEqual(instance.date_modified, old_mocked_now)
        self.assertEqual(
            instance.json.get("_date_modified"), old_mocked_now.isoformat()
        )

        # After saving the date_modified in json should update
        mocked_now = datetime(2023, 9, 21, 9, 3, 0, tzinfo=timezone.utc)

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
        mock_time.return_value = datetime.utcnow().replace(tzinfo=timezone.utc)
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

    def test_query_filter_by_datetime_field(self):
        self._publish_transportation_form()
        now = datetime(2014, 1, 1, tzinfo=timezone.utc)
        times = [
            now,
            now + timedelta(seconds=1),
            now + timedelta(seconds=2),
            now + timedelta(seconds=3),
        ]
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

    @override_settings(ASYNC_POST_SUBMISSION_PROCESSING_ENABLED=True)
    @patch("onadata.apps.logger.models.instance.save_full_json_async.apply_async")
    def test_light_tasks_synchronous(self, mock_json_async):
        """Metadata from light tasks is always processed synchronously"""
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        mock_json_async.assert_called()
        # _notes, _tags, _attachments should be missing since getting related
        # objects is performance intensive and should be handled async. Here
        # we mock the async task to simulate a failed async job
        self.assertEqual(
            instance.json,
            {
                "_id": instance.pk,
                "_uuid": "5b2cc313-fc09-437e-8149-fcd32f695d41",
                "image1": "1335783522563.jpg",
                "_edited": False,
                "_status": "submitted_via_web",
                "_version": "2014111",
                "_duration": "",
                "_xform_id": instance.xform.pk,
                "_geolocation": [None, None],
                "_media_count": 0,
                "_total_media": 1,
                "_submitted_by": "bob",
                "_date_modified": instance.date_modified.isoformat(),
                "meta/instanceID": "uuid:5b2cc313-fc09-437e-8149-fcd32f695d41",
                "_submission_time": instance.date_created.isoformat(),
                "_xform_id_string": "transportation_2011_07_25",
                "_bamboo_dataset_id": "",
                "_media_all_received": False,
                "transport/available_transportation_types_to_referral_facility": "none",
            },
        )

    def test_create_entity(self):
        """An Entity is created from a submission"""
        self.project = get_user_default_project(self.user)
        xform = self._publish_registration_form(self.user)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        entity_list = EntityList.objects.get(name="trees")

        self.assertEqual(entity.entity_list, entity_list)

        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
            "label": "300cm purpleheart",
        }

        self.assertDictEqual(entity.json, expected_json)
        self.assertEqual(str(entity.uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")
        self.assertEqual(entity.history.count(), 1)

        entity_history = entity.history.first()
        registration_form = RegistrationForm.objects.get(xform=xform)

        self.assertEqual(entity_history.registration_form, registration_form)
        self.assertEqual(entity_history.instance, instance)
        self.assertEqual(entity_history.xml, instance.xml)
        self.assertDictEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, xform.version)
        self.assertEqual(entity_history.created_by, instance.user)

    def test_create_entity_false(self):
        """An Entity is not created if create_if evaluates to false"""
        project = get_user_default_project(self.user)
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      | create_if                |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})| false()                  |                                            |"""
        self._publish_markdown(
            md,
            self.user,
            project,
            id_string="trees_registration",
            title="Trees registration",
        )
        xform = XForm.objects.all().order_by("-pk").first()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="false" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 0)

    def test_create_entity_true(self):
        """An Entity is created if create_if evaluates to true"""
        project = get_user_default_project(self.user)
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      | create_if                |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})| true()                  |                                            |"""
        self._publish_markdown(
            md,
            self.user,
            project,
            id_string="trees_registration",
            title="Trees registration",
        )
        xform = XForm.objects.all().order_by("-pk").first()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="true" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 1)

    def test_registration_form_inactive(self):
        """When the RegistrationForm is inactive, Entity should not be created"""
        xform = self._publish_registration_form(self.user)
        registration_form = xform.registration_forms.first()
        # Deactivate registration form
        registration_form.is_active = False
        registration_form.save()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 0)

    def _simulate_existing_entity(self):
        if not hasattr(self, "project"):
            self.project = get_user_default_project(self.user)

        self.entity_list, _ = EntityList.objects.get_or_create(
            name="trees", project=self.project
        )
        self.entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

    def test_update_entity(self):
        """An Entity is updated from a submission"""
        self._simulate_existing_entity()
        xform = self._publish_entity_update_form(self.user)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)
        # Update XForm is a RegistrationForm
        self.assertEqual(RegistrationForm.objects.filter(xform=xform).count(), 1)
        # No new Entity created
        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "300cm purpleheart",
        }

        self.assertDictEqual(entity.json, expected_json)

        entity_history = entity.history.first()
        registration_form = RegistrationForm.objects.get(xform=xform)

        self.assertEqual(entity_history.registration_form, registration_form)
        self.assertEqual(entity_history.instance, instance)
        self.assertEqual(entity_history.xml, xml)
        self.assertDictEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, xform.version)
        self.assertEqual(entity_history.created_by, instance.user)
        # New property is part of EntityList properties
        self.assertTrue("latest_visit" in entity.entity_list.properties)

    def test_update_entity_label(self):
        """An Entity label is updated from a submission"""
        # Simulate existing Entity
        self._simulate_existing_entity()
        # Update Entity via submission
        md = """
        | survey  |
        |         | type                           | name          | label                    | save_to                                 |
        |         | select_one_from_file trees.csv | tree          | Select the tree          |                                         |
        |         | integer                        | circumference | Tree circumference in cm | circumference_cm                        |
        |         | date                           | today         | Today's date             | latest_visit                            |
        | settings|                                |               |                          |                                         |
        |         | form_title                     | form _id      | version                  | instance_name                           |
        |         | Trees update                   | trees_update  | 2024050801               | concat(${circumference}, "cm ", ${tree})|
        | entities| list_name                      | entity_id     | label                    |                                         |
        |         | trees                          | ${tree}       | concat(${circumference}, "cm updated")|                            |                                         |
        """
        self._publish_markdown(
            md,
            self.user,
            self.project,
            id_string="trees_update",
            title="Trees update",
        )
        updating_xform = XForm.objects.all().order_by("-pk").first()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion="">'
            "<label>30cm updated</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=updating_xform)

        self.entity.refresh_from_db()

        self.assertEqual(
            self.entity.json,
            {
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "latest_visit": "2024-05-28",
                "circumference_cm": 30,
                "label": "30cm updated",
            },
        )

    def test_update_entity_false(self):
        """Entity not updated if update_if evaluates to false"""
        # Simulate existing Entity
        self._simulate_existing_entity()
        # If expression evaluates to false, Entity should not be updated
        md = """
        | survey  |
        |         | type                           | name          | label                    | save_to                                 |
        |         | select_one_from_file trees.csv | tree          | Select the tree          |                                         |
        |         | integer                        | circumference | Tree circumference in cm | circumference_cm                        |
        |         | date                           | today         | Today's date             | latest_visit                            |
        | settings|                                |               |                          |                                         |
        |         | form_title                     | form _id      | version                  | instance_name                           |
        |         | Trees update                   | trees_update  | 2024050801               | concat(${circumference}, "cm ", ${tree})|
        | entities| list_name                      | entity_id     | update_if                |                                         |
        |         | trees                          | ${tree}       | false()                  |                                         |
        """
        self._publish_markdown(
            md,
            self.user,
            self.project,
            id_string="trees_update",
            title="Trees update",
        )
        updating_xform = XForm.objects.all().order_by("-pk").first()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="false" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=updating_xform)
        expected_json = self.entity.json
        self.entity.refresh_from_db()

        self.assertEqual(self.entity.json, expected_json)

    def test_update_entity_true(self):
        """Entity updated if update_if evaluates to true"""
        self._simulate_existing_entity()
        md = """
        | survey  |
        |         | type                           | name          | label                    | save_to                                 |
        |         | select_one_from_file trees.csv | tree          | Select the tree          |                                         |
        |         | integer                        | circumference | Tree circumference in cm | circumference_cm                        |
        |         | date                           | today         | Today's date             | latest_visit                            |
        | settings|                                |               |                          |                                         |
        |         | form_title                     | form _id      | version                  | instance_name                           |
        |         | Trees update                   | trees_update  | 2024050801               | concat(${circumference}, "cm ", ${tree})|
        | entities| list_name                      | entity_id     | update_if                |                                         |
        |         | trees                          | ${tree}       | true()                  |                                         |
        """
        self._publish_markdown(
            md,
            self.user,
            self.project,
            id_string="trees_update",
            title="Trees update",
        )
        updating_xform = XForm.objects.all().order_by("-pk").first()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" '
            'update="true" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=updating_xform)
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "300cm purpleheart",
        }
        self.entity.refresh_from_db()

        self.assertDictEqual(self.entity.json, expected_json)

    def test_entity_create_update_true(self):
        """Both create_if and update_if evaluate to true"""
        self.project = get_user_default_project(self.user)
        md = """
        | survey  |
        |         | type                           | name          | label                    | save_to                                 |                                         |
        |         | select_one_from_file trees.csv | tree          | Select the tree          |                                         |                                         |
        |         | integer                        | circumference | Tree circumference in cm | circumference_cm                        |                                         |
        |         | date                           | today         | Today's date             | latest_visit                            |                                         |
        | settings|                                |               |                          |                                         |                                         |
        |         | form_title                     | form _id      | version                  | instance_name                           |                                         |
        |         | Trees update                   | trees_update  | 2024050801               | concat(${circumference}, "cm ", ${tree})|                                         |
        | entities| list_name                      | entity_id     | update_if                | create_if                               | label                                   |
        |         | trees                          | ${tree}       | true()                   | true()                                  | concat(${circumference}, "cm ", ${tree})|
        """
        self._publish_markdown(
            md,
            self.user,
            self.project,
            id_string="trees_update",
            title="Trees update",
        )
        xform = XForm.objects.all().order_by("-pk").first()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" '
            'update="true" create="true" baseVersion="">'
            "<label>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )

        # If Entity, does not exist, we create one
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        expected_json = {
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "30cm dbee4c32-a922-451c-9df7-42f40bf78f48",
        }
        self.assertDictEqual(entity.json, expected_json)

        # If Entity exists, we update
        Instance.objects.all().delete()
        Entity.objects.all().delete()
        # Simulate existsing Entity
        self._simulate_existing_entity()
        Instance.objects.create(xml=xml, user=self.user, xform=xform)
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "30cm dbee4c32-a922-451c-9df7-42f40bf78f48",
        }
        self.entity.refresh_from_db()
        # No new Entity should be created
        self.assertEqual(Entity.objects.count(), 1)
        self.assertDictEqual(self.entity.json, expected_json)

    def test_update_entity_via_instance_update(self):
        """Entity is updated if Instance from updating form is updated"""
        self._simulate_existing_entity()
        xform = self._publish_entity_update_form(self.user)
        # Update Entity via Instance creation
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)
        entity = Entity.objects.first()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "300cm purpleheart",
        }

        self.assertDictEqual(entity.json, expected_json)
        # Update Entity via Instance update
        instance = Instance.objects.get(
            pk=instance.pk
        )  # Get anew from DB to update Instance._parser
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>32</circumference>"  # Update to 32
            "<today>2024-06-19</today>"
            "<meta>"
            "<instanceID>uuid:fa6bcdce-e344-4dbd-9227-0f1cbdddb09c</instanceID>"
            "<instanceName>32cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion="">'
            "<label>32cm purpleheart</label>"
            "</entity>"
            "<deprecatedID>uuid:45d27780-48fd-4035-8655-9332649385bd</deprecatedID>"
            "</meta>"
            "</data>"
        )
        instance.xml = xml
        instance.uuid = "fa6bcdce-e344-4dbd-9227-0f1cbdddb09c"
        instance.save()
        entity.refresh_from_db()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-06-19",
            "circumference_cm": 32,
            "label": "32cm purpleheart",
        }
        self.assertDictEqual(entity.json, expected_json)

    def test_create_entity_exists(self):
        """Attempting to create an Entity that already exists fails"""
        self._simulate_existing_entity()
        xform = self._publish_registration_form(self.user)
        # Attempt to create an Entity whose uuid exists, with different data
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>wallaba</species>"
            "<circumference>54</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>54cm wallaba</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>54cm wallaba</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=xform)
        # No new Entity should be created
        self.assertEqual(Entity.objects.count(), 1)
        # Existing Entity unchanged
        self.entity.refresh_from_db()
        self.assertEqual(
            self.entity.json,
            {
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
        )

    def test_submission_review_enabled_entity_create(self):
        """Submission review disables automatic creation of Entity"""
        self.project = get_user_default_project(self.user)
        xform = self._publish_registration_form(self.user)
        MetaData.submission_review(xform, "true")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )

        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 0)

    def test_submission_review_enabled_entity_update(self):
        """Submission review disables automatic update of an Entity

        Only an approved Instance will update an Entity
        """
        self._simulate_existing_entity()
        xform = self._publish_entity_update_form(self.user)
        MetaData.submission_review(xform, "true")

        # Try to update Entity via Instance creation
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)
        entity = Entity.objects.first()
        expected_json = {
            "label": "300cm purpleheart",
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
        }
        # Entity not updated
        self.assertDictEqual(entity.json, expected_json)
        # Approve submission
        SubmissionReview.objects.create(
            instance=instance, status=SubmissionReview.APPROVED
        )
        entity.refresh_from_db()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "300cm purpleheart",
        }
        self.assertDictEqual(entity.json, expected_json)

        # Update Entity via Instance update
        instance = Instance.objects.get(
            pk=instance.pk
        )  # Get anew from DB to update Instance._parser
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>32</circumference>"  # Update to 32
            "<today>2024-06-19</today>"
            "<meta>"
            "<instanceID>uuid:fa6bcdce-e344-4dbd-9227-0f1cbdddb09c</instanceID>"
            "<instanceName>32cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion="">'
            "<label>32cm purpleheart</label>"
            "</entity>"
            "<deprecatedID>uuid:45d27780-48fd-4035-8655-9332649385bd</deprecatedID>"
            "</meta>"
            "</data>"
        )
        instance.xml = xml
        instance.uuid = "fa6bcdce-e344-4dbd-9227-0f1cbdddb09c"
        instance.save()
        entity.refresh_from_db()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-06-19",
            "circumference_cm": 32,
            "label": "32cm purpleheart",
        }
        # Entity updated since the submission is already approved
        self.assertDictEqual(entity.json, expected_json)

    def test_parse_numbers(self):
        """Integers and decimals are parsed correctly"""
        md = """
        | survey |
        |        | type    | name        | label          |
        |        | integer | num_integer | I am an integer|
        |        | decimal | num_decimal | I am a decimal |
        """
        self._publish_markdown(md, self.user)
        xform = XForm.objects.order_by("-pk").first()
        xml = (
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="just_numbers" version="202401291157">'
            "<formhub>"
            "<uuid>bd4278ad2fd8418fba5e6a822e2623e7</uuid>"
            "</formhub>"
            "<num_integer>4</num_integer>"
            "<num_decimal>5.5</num_decimal>"
            "<meta>"
            "<instanceID>uuid:49d75027-405a-4e08-be71-db9a75c70fc2</instanceID>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, xform=xform)
        instance.refresh_from_db()

        self.assertEqual(instance.json["num_integer"], 4)
        self.assertEqual(instance.json["num_decimal"], 5.5)

        # Test 0
        xml = (
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="just_numbers" version="202401291157">'
            "<formhub>"
            "<uuid>bd4278ad2fd8418fba5e6a822e2623e7</uuid>"
            "</formhub>"
            "<num_integer>0</num_integer>"
            "<num_decimal>0.0</num_decimal>"
            "<meta>"
            "<instanceID>uuid:59d75027-405a-4e08-be71-db9a75c70fc2</instanceID>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, xform=xform)
        instance.refresh_from_db()
        self.assertEqual(instance.json["num_integer"], 0)
        self.assertEqual(instance.json["num_decimal"], 0.0)

        #  Test negatives
        xml = (
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="just_numbers" version="202401291157">'
            "<formhub>"
            "<uuid>bd4278ad2fd8418fba5e6a822e2623e7</uuid>"
            "</formhub>"
            "<num_integer>-1</num_integer>"
            "<num_decimal>-1.0</num_decimal>"
            "<meta>"
            "<instanceID>uuid:69d75027-405a-4e08-be71-db9a75c70fc2</instanceID>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, xform=xform)
        instance.refresh_from_db()
        self.assertEqual(instance.json["num_integer"], -1)
        self.assertEqual(instance.json["num_decimal"], -1.0)

    def test_xml_entity_node_missing(self):
        """Entity node missing in submission XML"""
        self.project = get_user_default_project(self.user)
        xform = self._publish_registration_form(self.user)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            "</meta>"
            "</data>"
        )
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        self.assertEqual(Entity.objects.count(), 0)

    def test_repeat_columns_registered(self):
        """Instance repeat columns are added to export columns register"""
        project = get_user_default_project(self.user)
        md = """
        | survey |
        |        | type         | name            | label               |
        |        | begin repeat | hospital_repeat |                     |
        |        | text         | hospital        | Name of hospital    |
        |        | begin repeat | child_repeat    |                     |
        |        | text         | name            | Child's name        |
        |        | decimal      | birthweight     | Child's birthweight |
        |        | end_repeat   |                 |                     |
        |        | end_repeat   |                 |                     |
        | settings|             |                 |                     |
        |         | form_title  | form_id         |                     |
        |         | Births      | births          |                     |
        """
        xform = self._publish_markdown(md, self.user, project)
        register = MetaData.objects.get(
            data_type="export_columns_register",
            object_id=xform.pk,
            content_type=ContentType.objects.get_for_model(xform),
        )
        # Default export columns are correctly registered
        merged_multiples_columns = json.loads(
            register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        expected_columns = OrderedDict(
            [
                (
                    "hospital_repeat",
                    [],
                ),
                (
                    "hospital_repeat/child_repeat",
                    [],
                ),
                ("meta/instanceID", None),
            ]
        )
        self.assertEqual(merged_multiples_columns, expected_columns)
        self.assertEqual(split_multiples_columns, expected_columns)

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            f"<formhub><uuid>{xform.uuid}</uuid></formhub>"
            "<hospital_repeat>"
            "<hospital>Aga Khan</hospital>"
            "<child_repeat>"
            "<name>Zakayo</name>"
            "<birthweight>3.3</birthweight>"
            "</child_repeat>"
            "<child_repeat>"
            "<name>Melania</name>"
            "<birthweight>3.5</birthweight>"
            "</child_repeat>"
            "</hospital_repeat>"
            "<hospital_repeat>"
            "<hospital>Mama Lucy</hospital>"
            "<child_repeat>"
            "<name>Winnie</name>"
            "<birthweight>3.1</birthweight>"
            "</child_repeat>"
            "</hospital_repeat>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "</meta>"
            "</data>"
        )
        # Repeats are registered on creation
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)
        register.refresh_from_db()
        merged_multiples_columns = json.loads(
            register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        expected_columns = OrderedDict(
            [
                (
                    "hospital_repeat",
                    ["hospital_repeat[1]/hospital", "hospital_repeat[2]/hospital"],
                ),
                (
                    "hospital_repeat/child_repeat",
                    [
                        "hospital_repeat[1]/child_repeat[1]/name",
                        "hospital_repeat[1]/child_repeat[1]/birthweight",
                        "hospital_repeat[1]/child_repeat[2]/name",
                        "hospital_repeat[1]/child_repeat[2]/birthweight",
                        "hospital_repeat[2]/child_repeat[1]/name",
                        "hospital_repeat[2]/child_repeat[1]/birthweight",
                    ],
                ),
                ("meta/instanceID", None),
            ]
        )

        self.assertEqual(merged_multiples_columns, expected_columns)
        self.assertEqual(split_multiples_columns, expected_columns)

        # Repeats are registered on update
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            f"<formhub><uuid>{xform.uuid}</uuid></formhub>"
            "<hospital_repeat>"
            "<hospital>Aga Khan</hospital>"
            "<child_repeat>"
            "<name>Zakayo</name>"
            "<birthweight>3.3</birthweight>"
            "</child_repeat>"
            "<child_repeat>"
            "<name>Melania</name>"
            "<birthweight>3.5</birthweight>"
            "</child_repeat>"
            "</hospital_repeat>"
            "<hospital_repeat>"
            "<hospital>Mama Lucy</hospital>"
            "<child_repeat>"
            "<name>Winnie</name>"
            "<birthweight>3.1</birthweight>"
            "</child_repeat>"
            "</hospital_repeat>"
            "<hospital_repeat>"
            "<hospital>Mp Shah</hospital>"
            "<child_repeat>"
            "<name>Ada</name>"
            "<birthweight>3.1</birthweight>"
            "</child_repeat>"
            "</hospital_repeat>"
            "<meta>"
            "<instanceID>uuid:51cb9e07-cfc7-413b-bc22-ee7adfa9dec4</instanceID>"
            "<deprecatedID>uuid:45d27780-48fd-4035-8655-9332649385bd</deprecatedID>"
            "</meta>"
            "</data>"
        )
        instance.xml = xml
        instance.uuid = "51cb9e07-cfc7-413b-bc22-ee7adfa9dec4"
        instance.save()
        register.refresh_from_db()
        merged_multiples_columns = json.loads(
            register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        expected_columns = OrderedDict(
            [
                (
                    "hospital_repeat",
                    [
                        "hospital_repeat[1]/hospital",
                        "hospital_repeat[2]/hospital",
                        "hospital_repeat[3]/hospital",
                    ],
                ),
                (
                    "hospital_repeat/child_repeat",
                    [
                        "hospital_repeat[1]/child_repeat[1]/name",
                        "hospital_repeat[1]/child_repeat[1]/birthweight",
                        "hospital_repeat[1]/child_repeat[2]/name",
                        "hospital_repeat[1]/child_repeat[2]/birthweight",
                        "hospital_repeat[2]/child_repeat[1]/name",
                        "hospital_repeat[2]/child_repeat[1]/birthweight",
                        "hospital_repeat[3]/child_repeat[1]/name",
                        "hospital_repeat[3]/child_repeat[1]/birthweight",
                    ],
                ),
                ("meta/instanceID", None),
            ]
        )

        self.assertEqual(merged_multiples_columns, expected_columns)
        self.assertEqual(split_multiples_columns, expected_columns)
