# -*- coding: utf-8 -*-
"""
Test /data API endpoint implementation.
"""
from __future__ import unicode_literals

import datetime
import json
import logging
import os
from builtins import open
from datetime import timedelta
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.core.cache import cache
from django.db.utils import OperationalError
from django.test import RequestFactory
from django.test.testcases import SerializeMixin
from django.test.utils import override_settings
from django.utils import timezone

import defusedxml.ElementTree as ET
import geojson
import requests
from django_digest.test import Client as DigestClient
from django_digest.test import DigestAuth
from flaky import flaky
from httmock import HTTMock, urlmatch
from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet,
    enketo_urls_mock,
)
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import (
    Attachment,
    Instance,
    SubmissionReview,
    SurveyType,
    XForm,
)
from onadata.apps.logger.models.instance import InstanceHistory, get_attachment_url
from onadata.apps.main import tests as main_tests
from onadata.apps.main.models import UserProfile
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import SUBMISSION_DELETED, XFORM
from onadata.libs import permissions as role
from onadata.libs.permissions import (
    DataEntryMinorRole,
    DataEntryOnlyRole,
    EditorMinorRole,
    EditorRole,
    ManagerRole,
    ReadOnlyRole,
)
from onadata.libs.serializers.submission_review_serializer import (
    SubmissionReviewSerializer,
)
from onadata.libs.utils.common_tags import MONGO_STRFTIME
from onadata.libs.utils.logger_tools import create_instance


@urlmatch(netloc=r"(.*\.)?enketo\.ona\.io$")
def enketo_edit_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = (
        '{"edit_url": "https://hmh2a.enketo.ona.io/edit/XA0bG8D'
        "f?instance_id=672927e3-9ad4-42bb-9538-388ea1fb6699&retu"
        'rnUrl=http://test.io/test_url", "code": 201}'
    )
    return response


@urlmatch(netloc=r"(.*\.)?enketo\.ona\.io$")
def enketo_mock_http_413(url, request):
    response = requests.Response()
    response.status_code = 413
    response._content = ""
    return response


def _data_list(formid):
    return [
        {
            "id": formid,
            "id_string": "transportation_2011_07_25",
            "title": "transportation_2011_07_25",
            "description": "",
            "url": "http://testserver/api/v1/data/%s" % formid,
        }
    ]


def _data_instance(dataid):
    return {
        "_bamboo_dataset_id": "",
        "_attachments": [],
        "_geolocation": [None, None],
        "_xform_id_string": "transportation_2011_07_25",
        "transport/available_transportation_types_to_referral_facility": "none",
        "_status": "submitted_via_web",
        "_id": dataid,
    }


# pylint: disable=too-many-public-methods
@override_settings(MEDIA_ROOT=os.path.join(settings.PROJECT_ROOT, "test_data_media/"))
class TestDataViewSet(SerializeMixin, TestBase):
    """
    Test /data API endpoint implementation.
    """
    lockfile = __file__

    def setUp(self):
        super().setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}

    def test_data(self):
        """Test DataViewSet list"""
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())

        dataid = self.xform.instances.all().order_by("id")[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(
            data, sorted(response.data, key=lambda x: x["_id"])[0]
        )

        data = {
            "_xform_id_string": "transportation_2011_07_25",
            "transport/available_transportation_types_to_referral_facility": "none",
            "_submitted_by": "bob",
        }
        view = DataViewSet.as_view({"get": "retrieve"})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    @override_settings(STREAM_DATA=True)
    def test_data_streaming(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)

        # expect streaming response
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        streaming_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )
        self.assertIsInstance(streaming_data, list)
        self.assertTrue(self.xform.instances.count())

        dataid = self.xform.instances.all().order_by("id")[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(
            data, sorted(streaming_data, key=lambda x: x["_id"])[0]
        )

        data = {
            "_xform_id_string": "transportation_2011_07_25",
            "transport/available_transportation_types_to_referral_facility": "none",
            "_submitted_by": "bob",
        }
        view = DataViewSet.as_view({"get": "retrieve"})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_catch_data_error(self):
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        query_str = [
            (
                '\'{"_submission_time":{'
                '"$and":[{"$gte":"2015-11-15T00:00:00"},'
                '{"$lt":"2015-11-16T00:00:00"}]}}'
            )
        ]

        data = {
            "query": query_str,
        }
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("detail"),
            "invalid regular expression: invalid character range\n",
        )

    def test_data_list_with_xform_in_delete_async_queue(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        initial_count = len(response.data)

        self.xform.deleted_at = timezone.now()
        self.xform.save()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(len(response.data), initial_count - 1)

    def test_numeric_types_are_rendered_as_required(self):
        """Test numeric types are rendered as numeric."""
        tutorial_folder = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "forms", "tutorial"
        )
        self._publish_xls_file_and_set_xform(
            os.path.join(tutorial_folder, "tutorial.xlsx")
        )

        instance_path = os.path.join(tutorial_folder, "instances", "1.xml")
        create_instance(self.user.username, open(instance_path, "rb"), [])

        self.assertEqual(self.xform.instances.count(), 1)

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        # check that ONLY values with numeric and decimal types are converted
        self.assertEqual(response.data[0].get("age"), 35)
        self.assertEqual(response.data[0].get("net_worth"), 100000.00)
        self.assertEqual(response.data[0].get("imei"), "351746052009472")

        # test when fields parameter is used.
        fields_query = {"fields": '["_id", "age", "net_worth", "imei"]'}
        request = self.factory.get("/", data=fields_query, **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200, response.data)
        # check that ONLY values with numeric and decimal types are converted
        self.assertEqual(response.data[0].get("age"), 35)
        self.assertEqual(response.data[0].get("net_worth"), 100000.00)
        self.assertEqual(response.data[0].get("imei"), "351746052009472")

    def test_data_jsonp(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid, format="jsonp")
        self.assertEqual(response.status_code, 200)
        response.render()
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("callback("))
        self.assertTrue(content.endswith(");"))
        self.assertEqual(len(response.data), 4)

    def _assign_user_role(self, user, role):
        # share bob's project with alice and give alice an editor role
        data = {"username": user.username, "role": role.name}
        request = self.factory.put("/", data=data, **self.extra)
        xform_view = XFormViewSet.as_view({"put": "share"})
        response = xform_view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 204)

        self.assertTrue(role.user_has_role(user, self.xform))

    def test_returned_data_is_based_on_form_permissions(self):
        # create a form and make submissions to it
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # create user alice
        user_alice = self._create_user("alice", "alice")
        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        # Enable meta perms
        data_value = "editor-minor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        self._assign_user_role(user_alice, DataEntryOnlyRole)

        alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % user_alice.auth_token.key}

        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        data = {"start": 1, "limit": 4}
        request = self.factory.get("/", data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        data = {"sort": 1}
        request = self.factory.get("/", data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        self._assign_user_role(user_alice, EditorMinorRole)
        # check that by default, alice can be able to access all the data

        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # change xform permission for users with editor role - they should
        # only view data that they submitted
        self.xform.save()

        # change user in 2 instances to be owned by alice - they should appear
        # as if they were submitted by alice
        for i in self.xform.instances.all()[:2]:
            i.user = user_alice
            i.save()

        # check that 2 instances were 'submitted by' alice
        instances_submitted_by_alice = self.xform.instances.filter(
            user=user_alice
        ).count()
        self.assertTrue(instances_submitted_by_alice, 2)

        # check that alice will only be able to see the data she submitted
        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # check that alice views only her data when querying data
        data = {
            "start": 0,
            "limit": 100,
            "sort": '{"_submission_time":1}',
            "query": "c",
        }
        request = self.factory.get("/", data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertListEqual(
            [r["_submitted_by"] for r in response.data], ["alice", "alice"]
        )

        data = {"start": 1, "limit": 1}
        request = self.factory.get("/", data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        data = {"sort": 1}
        request = self.factory.get("/", data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # change meta perms
        data_value = "editor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        self._assign_user_role(user_alice, EditorRole)

        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        self._assign_user_role(user_alice, ReadOnlyRole)

        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_xform_meta_permissions_not_affected_w_projects_perms(self):
        # create a form and make submissions to it
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # create user alice
        user_alice = self._create_user("alice", "alice")
        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        data = {"username": user_alice.username, "role": EditorRole.name}
        request = self.factory.put("/", data=data, **self.extra)
        project_view = ProjectViewSet.as_view({"put": "share"})
        response = project_view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 204)

        self.assertTrue(EditorRole.user_has_role(user_alice, self.xform))
        self._assign_user_role(user_alice, EditorMinorRole)
        MetaData.xform_meta_permission(self.xform, data_value="editor-minor|dataentry")

        self.assertFalse(EditorRole.user_has_role(user_alice, self.xform))

        alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % user_alice.auth_token.key}

        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(EditorRole.user_has_role(user_alice, self.xform))
        self.assertEqual(len(response.data), 0)

    def test_data_entryonly_can_submit_but_not_view(self):
        # create user alice
        user_alice = self._create_user("alice", "alice")
        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        # Enable meta perms
        data_value = "editor-minor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        DataEntryOnlyRole.add(user_alice, self.xform)
        DataEntryOnlyRole.add(user_alice, self.project)

        auth = DigestAuth("alice", "alice")

        paths = [
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            for s in self.surveys
        ]

        for path in paths:
            self._make_submission(path, auth=auth)

        alices_extra = {"HTTP_AUTHORIZATION": "Token %s" % user_alice.auth_token.key}

        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        DataEntryMinorRole.add(user_alice, self.xform)
        DataEntryMinorRole.add(user_alice, self.project)

        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        request = self.factory.get("/", **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_pagination(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        # no page param no pagination
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get(
            "/", data={"page": "1", "page_size": 2}, **self.extra
        )
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Link pagination headers are present and work as intended
        self.assertIn("Link", response)
        self.assertEqual(
            response["Link"], '<http://testserver/?page=2&page_size=2>; rel="next"'
        )

        request = self.factory.get("/", data={"page": 2, "page_size": 1}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Link", response)
        self.assertEqual(
            response["Link"],
            (
                '<http://testserver/?page=1&page_size=1>; rel="prev", '
                '<http://testserver/?page=3&page_size=1>; rel="next", '
                '<http://testserver/?page=4&page_size=1>; rel="last", '
                '<http://testserver/?page=1&page_size=1>; rel="first"'
            ),
        )

        request = self.factory.get("/", data={"page_size": "3"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        request = self.factory.get(
            "/", data={"page": "1", "page_size": "2"}, **self.extra
        )
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # invalid page returns a 404
        request = self.factory.get("/", data={"page": "invalid"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        # invalid page size is ignored
        request = self.factory.get("/", data={"page_size": "invalid"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # Query param returns correct pagination headers
        request = self.factory.get(
            "/", data={"page_size": "1", "query": "ambulance"}, **self.extra
        )
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Link", response)
        self.assertEqual(
            response["Link"], ('<http://testserver/?page=2&page_size=1>; rel="next"')
        )

    def test_sort_query_param_with_invalid_values(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        # without sort param
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        error_message = (
            "Expecting property name enclosed in "
            "double quotes: line 1 column 2 (char 1)"
        )

        request = self.factory.get("/", data={"sort": "{" ":}"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("detail"), error_message)

        request = self.factory.get("/", data={"sort": "{:}"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("detail"), error_message)

        request = self.factory.get("/", data={"sort": "{" ":" "}"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("detail"), error_message)

        # test sort with a key that os likely in the json data
        request = self.factory.get("/", data={"sort": "random"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_start_limit_no_records(self):
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        # no start, limit params
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get("/", data={"start": "1", "limit": 2}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_data_start_limit(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        # no start, limit params
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)
        self.assertTrue(response.has_header("ETag"))
        etag_data = response["Etag"]

        request = self.factory.get("/", data={"start": "1", "limit": 2}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertNotEqual(etag_data, response["Etag"])
        etag_data = response["Etag"]
        response.render()
        data = json.loads(response.content)
        self.assertEqual(
            [i["_uuid"] for i in data],
            [
                "f3d8dc65-91a6-4d0f-9e97-802128083390",
                "9c6f3468-cfda-46e8-84c1-75458e72805d",
            ],
        )

        request = self.factory.get("/", data={"start": "3", "limit": 1}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertNotEqual(etag_data, response["Etag"])
        etag_data = response["Etag"]
        response.render()
        data = json.loads(response.content)
        self.assertEqual(
            [i["_uuid"] for i in data], ["9f0a1508-c3b7-4c99-be00-9b237c26bcbf"]
        )

        request = self.factory.get("/", data={"limit": "3"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        self.assertNotEqual(etag_data, response["Etag"])
        etag_data = response["Etag"]

        request = self.factory.get("/", data={"start": "1", "limit": "2"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertNotEqual(etag_data, response["Etag"])

        # invalid start is ignored, all data is returned
        request = self.factory.get("/", data={"start": "invalid"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # invalid limit is ignored, all data is returned
        request = self.factory.get("/", data={"limit": "invalid"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # invalid start is ignored, all data is returned
        request = self.factory.get("/", data={"start": "", "limit": 10}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    @override_settings(STREAM_DATA=True)
    def test_paginate_and_sort_streaming_data(self):
        """
        Test that "sort" query param works as expected for paginated
        responses
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        # will result in a queryset due to the page and page_size params
        # hence paging and thus len(self.object_list) for length
        query_data = {"page_size": 3, "page": 1, "sort": '{"date_created":-1}'}
        request = self.factory.get("/", data=query_data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        streaming_data = json.loads(
            "".join([c.decode("utf-8") for c in response.streaming_content])
        )
        self.assertEqual(len(streaming_data), 3)

        # Test `date_created` field is sorted correctly
        expected_order = list(
            Instance.objects.filter(xform=self.xform)
            .order_by("-date_created")
            .values_list("id", flat=True)
        )
        items_in_order = [sub.get("_id") for sub in streaming_data]

        self.assertEqual(expected_order[:3], items_in_order)
        self.assertTrue(response.has_header("ETag"))

        # Data fetched for page 2 should return a different list
        data = {"page_size": 3, "page": 2, "sort": '{"date_created":-1}'}
        request2 = self.factory.get("/", data=data, **self.extra)
        response2 = view(request2, pk=formid)
        self.assertEqual(response2.status_code, 200)
        streaming_data = json.loads(
            "".join([c.decode("utf-8") for c in response2.streaming_content])
        )
        self.assertEqual(len(streaming_data), 1)
        pg_2_items_in_order = [sub.get("_id") for sub in streaming_data]
        self.assertEqual(expected_order[3:], pg_2_items_in_order)

    def test_data_start_limit_sort(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        data = {"start": 1, "limit": 2, "sort": '{"_id":1}'}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertTrue(response.has_header("ETag"))
        response.render()
        data = json.loads(response.content)
        self.assertEqual(
            [i["_uuid"] for i in data],
            [
                "f3d8dc65-91a6-4d0f-9e97-802128083390",
                "9c6f3468-cfda-46e8-84c1-75458e72805d",
            ],
        )

    def test_filter_pending_submission_reviews(self):
        """
        Test that a user is able to query for null
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # Create approved  submission review for one instance
        instances = self.xform.instances.all().order_by("pk")
        instance = instances[0]
        self.assertFalse(instance.has_a_review)

        self._create_user_and_login("bob", "1234")
        ManagerRole.add(self.user, self.xform.instances.all().order_by("pk")[0].xform)

        data = {
            "note": "Approved!",
            "instance": instance.id,
            "status": SubmissionReview.APPROVED,
        }

        serializer_instance = SubmissionReviewSerializer(
            data=data, context={"request": request}
        )
        serializer_instance.is_valid()
        serializer_instance.save()
        instance.refresh_from_db()

        # Confirm xform submission review enabled
        self.assertTrue(instance.has_a_review)
        # Confirm instance json now has _review_status field
        self.assertIn("_review_status", dict(instance.json))
        # Confirm instance submission review status
        self.assertEqual("1", instance.json["_review_status"])

        # Query xform data by submission review status 3
        query_str = '{"_review_status": 3}'
        request = self.factory.get(f"/?query={query_str}", **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        # Should not return any submissions
        self.assertEqual(len(response.data), 0)

        # Query xform data by NULL submission review
        query_str = '{"_review_status": null}'
        request = self.factory.get(f"/?query={query_str}", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    @override_settings(STREAM_DATA=True)
    def test_data_start_limit_sort_json_field(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        # will result in a generator due to the JSON sort
        # hence self.total_count will be used for length in streaming response
        data = {
            "start": 1,
            "limit": 2,
            "sort": '{"transport/available_transportation_types_to_referral_facility":1}',  # noqa
        }
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header("ETag"))
        data = json.loads(
            "".join([c.decode("utf-8") for c in response.streaming_content])
        )
        self.assertEqual(len(data), 2)
        self.assertEqual(
            [i["_uuid"] for i in data],
            [
                "f3d8dc65-91a6-4d0f-9e97-802128083390",
                "5b2cc313-fc09-437e-8149-fcd32f695d41",
            ],
        )

        # will result in a queryset due to the page and page_size params
        # hence paging and thus len(self.object_list) for length
        data = {
            "page": 1,
            "page_size": 2,
        }
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = json.loads(
            "".join([c.decode("utf-8") for c in response.streaming_content])
        )
        self.assertEqual(len(data), 2)

        data = {
            "page": 1,
            "page_size": 3,
        }
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = json.loads(
            "".join([c.decode("utf-8") for c in response.streaming_content])
        )
        self.assertEqual(len(data), 3)

    def test_data_anon(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/")
        formid = self.xform.pk
        response = view(request, pk=formid)
        # data not found for anonymous access to private data
        self.assertEqual(response.status_code, 404)

        self.xform.shared = True
        self.xform.save()
        response = view(request, pk=formid)
        # access to a shared form but private data
        self.assertEqual(response.status_code, 404)

        self.xform.shared_data = True
        self.xform.save()
        response = view(request, pk=formid)
        # access to a public data
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by("id")[0].pk
        data = _data_instance(dataid)

        self.assertDictContainsSubset(
            data, sorted(response.data, key=lambda x: x["_id"])[0]
        )

        data = {
            "_xform_id_string": "transportation_2011_07_25",
            "transport/available_transportation_types_to_referral_facility": "none",
            "_submitted_by": "bob",
        }
        view = DataViewSet.as_view({"get": "retrieve"})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_data_public(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_public_anon_user(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/")
        response = view(request, pk="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_user_public(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_bad_formid(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        formid = 98918
        self.assertEqual(XForm.objects.filter(pk=formid).count(), 0)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        formid = "INVALID"
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get("Cache-Control"), None)
        error_message = "Invalid form ID. It must be a positive integer"
        self.assertEqual(str(response.data["detail"]), error_message)

    def test_data_bad_dataid(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = "INVALID"
        data = _data_instance(dataid)
        view = DataViewSet.as_view({"get": "retrieve"})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get("Cache-Control"), None)

    def test_filter_by_submission_time_and_submitted_by(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by("pk")[0]
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = '{"_submission_time": {"$gte": "%s"},' ' "_submitted_by": "%s"}' % (
            submission_time,
            "bob",
        )
        data = {"query": query_str, "limit": 2, "sort": []}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_date_modified(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by("pk")[0]
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        instance = self.xform.instances.all().order_by("-date_created")[0]
        date_modified = instance.date_modified.isoformat()

        query_str = '{"_date_modified": {"$gte": "%s"},' ' "_submitted_by": "%s"}' % (
            date_modified,
            "bob",
        )
        data = {"query": query_str}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        expected_count = self.xform.instances.filter(
            date_modified__gte=date_modified
        ).count()
        self.assertEqual(len(response.data), expected_count)

    def test_filter_by_submission_time_and_submitted_by_with_data_arg(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by("pk")[0]
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = '{"_submission_time": {"$gte": "%s"},' ' "_submitted_by": "%s"}' % (
            submission_time,
            "bob",
        )
        data = {"data": query_str, "limit": 2, "sort": []}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_submission_time_date_formats(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        data = {"query": '{"_submission_time":{"$gt":"2018-04-19"}}'}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        data = {"query": '{"_submission_time":{"$gt":"2018-04-19T14:46:32"}}'}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

    def test_data_with_query_parameter(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by("pk")[0]
        dataid = instance.pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        query_str = '{"_id": "%s"}' % dataid
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = '{"_submission_time": {"$gte": "%s"}}' % submission_time
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # reorder date submitted
        start_time = datetime.datetime(2015, 12, 2)
        curr_time = start_time
        for inst in self.xform.instances.all():
            inst.date_created = curr_time
            inst.json = instance.get_full_dict()
            inst.save()
            inst.parsed_instance.save()
            curr_time += timedelta(days=1)

        first_datetime = start_time.strftime(MONGO_STRFTIME)
        second_datetime = start_time + timedelta(days=1, hours=20)

        query_str = (
            '{"_submission_time": {"$gte": "'
            + first_datetime
            + '", "$lte": "'
            + second_datetime.strftime(MONGO_STRFTIME)
            + '"}}'
        )

        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        query_str = '{"_id: "%s"}' % dataid
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("detail"),
            "Expecting ':' delimiter: line 1 column 9 (char 8)",
        )

        query_str = (
            '{"transport/available_transportation'
            '_types_to_referral_facility": {"$i": "%s"}}' % "ambula"
        )
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # search a text
        query_str = "uuid:9f0a1508-c3b7-4c99-be00-9b237c26bcbf"
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # search an integer
        query_str = 7545
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_anon_data_list(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/")
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_add_form_tag_propagates_to_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        self._make_submissions()
        xform = XForm.objects.all()[0]
        pk = xform.id
        view = XFormViewSet.as_view(
            {"get": "labels", "post": "labels", "delete": "labels"}
        )
        data_view = DataViewSet.as_view(
            {
                "get": "list",
            }
        )
        # no tags
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.data, [])

        request = self.factory.get("/", {"tags": "hello"}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get("/", {"not_tagged": "hello"}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # add tag "hello"
        request = self.factory.post("/", data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, ["hello"])
        for i in self.xform.instances.all():
            self.assertIn("hello", i.tags.names())

        request = self.factory.get("/", {"tags": "hello"}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        request = self.factory.get("/", {"not_tagged": "hello"}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # remove tag "hello"
        request = self.factory.delete("/", data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk, label="hello")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        for i in self.xform.instances.all():
            self.assertNotIn("hello", i.tags.names())

    def test_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        self._make_submissions()
        submission_count = self.xform.instances.count()
        pk = self.xform.pk
        i = self.xform.instances.all()[0]
        dataid = i.pk
        data_view = DataViewSet.as_view(
            {
                "get": "list",
            }
        )
        view = DataViewSet.as_view(
            {"get": "labels", "post": "labels", "delete": "labels"}
        )

        # no tags
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        request = self.factory.get("/", {"tags": "hello"}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get("/", {"not_tagged": "hello"}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), submission_count)

        # add tag "hello"
        request = self.factory.post("/", data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, ["hello"])
        self.assertIn("hello", Instance.objects.get(pk=dataid).tags.names())

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.data, ["hello"])

        request = self.factory.get("/", {"tags": "hello"}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        request = self.factory.get("/", {"not_tagged": "hello"}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), submission_count - 1)

        # remove tag "hello"
        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=pk, dataid=dataid, label="hello")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertNotIn("hello", Instance.objects.get(pk=dataid).tags.names())

    def test_labels_action_with_params(self):
        self._make_submissions()
        xform = XForm.objects.all()[0]
        pk = xform.id
        dataid = xform.instances.all()[0].id
        view = DataViewSet.as_view({"get": "labels"})

        request = self.factory.get("/", **self.extra)
        response = view(request, pk=pk, dataid=dataid, label="hello")
        self.assertEqual(response.status_code, 200)

    def test_data_list_filter_by_user(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        bobs_data = _data_list(formid)[0]

        previous_user = self.user
        self._create_user_and_login("alice", "alice")
        self.assertEqual(self.user.username, "alice")
        self.assertNotEqual(previous_user, self.user)

        ReadOnlyRole.add(self.user, self.xform)

        # publish alice's form
        self._publish_transportation_form()

        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        formid = self.xform.pk
        alice_data = _data_list(formid)[0]

        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        # should be both bob's and alice's form
        self.assertEqual(
            sorted(response.data, key=lambda x: x["id"]),
            sorted([bobs_data, alice_data], key=lambda x: x["id"]),
        )

        # apply filter, see only bob's forms
        request = self.factory.get("/", data={"owner": "bob"}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [bobs_data])

        # apply filter, see only alice's forms
        request = self.factory.get("/", data={"owner": "alice"}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [alice_data])

        # apply filter, see a non existent user
        request = self.factory.get("/", data={"owner": "noone"}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_get_enketo_edit_url(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "enketo"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by("id")[0].pk

        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get("Cache-Control"), None)
        # add data check
        self.assertEqual(response.data, {"detail": "return_url not provided."})

        request = self.factory.get(
            "/", data={"return_url": "http://test.io/test_url"}, **self.extra
        )

        with HTTMock(enketo_edit_mock):
            response = view(request, pk=formid, dataid=dataid)
            self.assertEqual(
                response.data["url"],
                "https://hmh2a.enketo.ona.io/edit/XA0bG8Df?instance_id="
                "672927e3-9ad4-42bb-9538-388ea1fb6699&returnUrl=http://test"
                ".io/test_url",
            )

        with HTTMock(enketo_mock_http_413):
            response = view(request, pk=formid, dataid=dataid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get("Cache-Control"), None)

    def test_get_form_public_data(self):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/")
        formid = self.xform.pk
        response = view(request, pk=formid)

        # data not found for anonymous access to private data
        self.assertEqual(response.status_code, 404)
        self.xform.shared_data = True
        self.xform.save()

        # access to a public data as anon
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by("id")[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(
            data, sorted(response.data, key=lambda x: x["_id"])[0]
        )

        # access to a public data as other user
        self._create_user_and_login("alice", "alice")
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by("id")[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(
            data, sorted(response.data, key=lambda x: x["_id"])[0]
        )

    def test_same_submission_with_different_attachments(self):
        """
        Test same submission with different attachments on each request.
        """
        images_md = """
        | survey |
        |        | type  | name   | label |
        |        | photo | image1 | Pic 1 |
        |        | photo | image2 | Pic 2 |
        """
        xform = self._publish_markdown(images_md, self.user)
        submission_file = NamedTemporaryFile(delete=False)
        with open(submission_file.name, "w") as xml_file:
            xml_file.write(
                "<?xml version='1.0'?><data id=\"%s\">"
                "<image1>1335783522563.jpg</image1>"
                "<image2>1442323232322.jpg</image2>"
                "<meta><instanceID>uuid:729f173c688e482486a48661700455ff"
                "</instanceID></meta></data>" % (xform.id_string)
            )
        media_file = "1335783522563.jpg"
        self._make_submission_w_attachment(
            submission_file.name,
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                self.surveys[0],
                media_file,
            ),
        )
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = xform.pk
        data = {
            "id": formid,
            "id_string": xform.id_string,
            "title": xform.title,
            "description": "",
            "url": "http://testserver/api/v1/data/%s" % formid,
        }
        self.assertEqual(response.data[1], data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        instance = xform.instances.all().order_by("id")[0]
        dataid = instance.pk
        attachment = instance.attachments.all().first()

        data = {
            "_bamboo_dataset_id": "",
            "_attachments": [
                {
                    "download_url": get_attachment_url(attachment),
                    "small_download_url": get_attachment_url(attachment, "small"),
                    "medium_download_url": get_attachment_url(attachment, "medium"),
                    "mimetype": attachment.mimetype,
                    "instance": attachment.instance.pk,
                    "filename": attachment.media_file.name,
                    "name": attachment.name,
                    "id": attachment.pk,
                    "xform": xform.id,
                }
            ],
            "_geolocation": [None, None],
            "_xform_id_string": xform.id_string,
            "_status": "submitted_via_web",
            "_id": dataid,
            "image1": "1335783522563.jpg",
        }
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        patch_value = "onadata.libs.utils.logger_tools.get_filtered_instances"
        with patch(patch_value) as get_filtered_instances:
            get_filtered_instances.return_value = Instance.objects.filter(
                uuid="#doesnotexist"
            )
            media_file = "1442323232322.jpg"
            self._make_submission_w_attachment(
                submission_file.name,
                os.path.join(
                    self.this_directory,
                    "fixtures",
                    "transportation",
                    "instances",
                    self.surveys[0],
                    media_file,
                ),
            )
            attachment = Attachment.objects.get(name=media_file)

            data["_attachments"] = data.get("_attachments") + [
                {
                    "download_url": get_attachment_url(attachment),
                    "small_download_url": get_attachment_url(attachment, "small"),
                    "medium_download_url": get_attachment_url(attachment, "medium"),
                    "mimetype": attachment.mimetype,
                    "instance": attachment.instance.pk,
                    "filename": attachment.media_file.name,
                    "name": attachment.name,
                    "id": attachment.pk,
                    "xform": xform.id,
                }
            ]
            self.maxDiff = None
            response = view(request, pk=formid)
            self.assertDictContainsSubset(sorted([data])[0], sorted(response.data)[0])
            self.assertEqual(response.status_code, 200)
        submission_file.close()
        os.unlink(submission_file.name)

    def test_data_w_attachment(self):
        self._submit_transport_instance_w_attachment()

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by("id")[0].pk

        data = {
            "_bamboo_dataset_id": "",
            "_attachments": [
                {
                    "download_url": get_attachment_url(self.attachment),
                    "small_download_url": get_attachment_url(self.attachment, "small"),
                    "medium_download_url": get_attachment_url(
                        self.attachment, "medium"
                    ),
                    "mimetype": self.attachment.mimetype,
                    "instance": self.attachment.instance.pk,
                    "filename": self.attachment.media_file.name,
                    "name": self.attachment.name,
                    "id": self.attachment.pk,
                    "xform": self.xform.id,
                }
            ],
            "_geolocation": [None, None],
            "_xform_id_string": "transportation_2011_07_25",
            "transport/available_transportation_types_to_referral_facility": "none",
            "_status": "submitted_via_web",
            "_id": dataid,
        }
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            "_xform_id_string": "transportation_2011_07_25",
            "transport/available_transportation_types_to_referral_facility": "none",
            "_submitted_by": "bob",
        }
        view = DataViewSet.as_view({"get": "retrieve"})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    def test_delete_submission(self, send_message_mock):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by("id")[0].pk
        view = DataViewSet.as_view({"delete": "destroy", "get": "list"})
        # get the first xform instance returned
        first_xform_instance = self.xform.instances.filter(pk=dataid)
        self.assertEqual(first_xform_instance[0].deleted_by, None)

        # 4 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 204)
        first_xform_instance = self.xform.instances.filter(pk=dataid)
        self.assertEqual(first_xform_instance[0].deleted_by, request.user)
        # message sent upon delete
        self.assertTrue(send_message_mock.called)
        send_message_mock.assert_called_with(
            instance_id=dataid,
            target_id=formid,
            target_type=XFORM,
            user=request.user,
            message_verb=SUBMISSION_DELETED,
        )

        # second delete of same submission should return 404
        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 404)

        # remaining 3 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)

        self._create_user_and_login(username="alice", password="alice")
        # Managers can delete
        role.ManagerRole.add(self.user, self.xform)
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        request = self.factory.delete("/", **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None).order_by("id")[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 2)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    @patch("onadata.apps.viewer.signals._post_process_submissions")
    def test_post_save_signal_on_submission_deletion(self, mock, send_message_mock):
        # test that post_save_submission signal is sent
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
        )
        self._make_submission(xml_submission_file_path)
        view = DataViewSet.as_view({"delete": "destroy", "get": "list"})

        self.assertEqual(self.response.status_code, 201)

        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by("id")[0].pk
        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        instance = self.xform.instances.first()
        self.assertTrue(mock.called)
        mock.assert_called_once_with(instance)
        self.assertEqual(mock.call_count, 1)
        # check that call_count is still one after saving instance again
        instance.save()
        self.assertEqual(mock.call_count, 1)
        self.assertTrue(send_message_mock.called)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    def test_deletion_of_bulk_submissions(self, send_message_mock):

        self._make_submissions()
        self.xform.refresh_from_db()
        formid = self.xform.pk
        initial_count = self.xform.instances.filter(deleted_at=None).count()
        self.assertEqual(initial_count, 4)
        self.assertEqual(self.xform.num_of_submissions, 4)

        view = DataViewSet.as_view({"delete": "destroy"})

        # test with invalid instance id's
        data = {"instance_ids": "john,doe"}
        request = self.factory.delete("/", data=data, **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("detail"), "Invalid data ids were provided.")
        self.xform.refresh_from_db()
        current_count = self.xform.instances.filter(deleted_at=None).count()
        self.assertEqual(current_count, initial_count)
        self.assertEqual(current_count, 4)
        self.assertEqual(self.xform.num_of_submissions, 4)

        # test with valid instance id's
        records_to_be_deleted = self.xform.instances.all()[:2]
        instance_ids = ",".join([str(i.pk) for i in records_to_be_deleted])
        data = {"instance_ids": instance_ids}

        request = self.factory.delete("/", data=data, **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data.get("message"),
            "%d records were deleted" % len(records_to_be_deleted),
        )
        self.assertTrue(send_message_mock.called)
        send_message_mock.called_with(
            [str(i.pk) for i in records_to_be_deleted],
            formid,
            XFORM,
            request.user,
            SUBMISSION_DELETED,
        )
        self.xform.refresh_from_db()
        current_count = self.xform.instances.filter(deleted_at=None).count()
        self.assertNotEqual(current_count, initial_count)
        self.assertEqual(current_count, 2)
        self.assertEqual(self.xform.num_of_submissions, 2)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    def test_delete_submission_inactive_form(self, send_message_mock):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by("id")[0].pk
        view = DataViewSet.as_view(
            {
                "delete": "destroy",
            }
        )

        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # make form inactive
        self.xform.downloadable = False
        self.xform.save()

        dataid = self.xform.instances.filter(deleted_at=None).order_by("id")[0].pk

        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(send_message_mock.called)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    def test_delete_submissions(self, send_message_mock):
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)
        # Add multiple submissions
        for x in range(1, 11):
            path = os.path.join(
                settings.PROJECT_ROOT,
                "libs",
                "tests",
                "utils",
                "fixtures",
                "tutorial",
                "instances",
                "uuid{}".format(x),
                "submission.xml",
            )
            self._make_submission(path)
            x += 1
        self.xform.refresh_from_db()
        formid = self.xform.pk
        initial_count = self.xform.instances.filter(deleted_at=None).count()
        self.assertEqual(initial_count, 9)
        self.assertEqual(self.xform.num_of_submissions, 9)

        view = DataViewSet.as_view({"delete": "destroy"})
        deleted_instances_subset = self.xform.instances.all()[:6]
        instance_ids = ",".join([str(i.pk) for i in deleted_instances_subset])
        data = {"instance_ids": instance_ids, "delete_all": False}

        request = self.factory.delete("/", data=data, **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data.get("message"),
            "%d records were deleted" % len(deleted_instances_subset),
        )
        self.assertTrue(send_message_mock.called)
        send_message_mock.called_with(
            [str(i.pk) for i in deleted_instances_subset],
            formid,
            XFORM,
            request.user,
            SUBMISSION_DELETED,
        )

        # Test that num of submissions for the form is successfully updated
        self.xform.refresh_from_db()
        current_count = self.xform.instances.filter(deleted_at=None).count()
        self.assertNotEqual(current_count, initial_count)
        self.assertEqual(current_count, 3)
        self.assertEqual(self.xform.num_of_submissions, 3)

        # Test delete_all submissions for the form
        data = {"delete_all": True}
        request = self.factory.delete("/", data=data, **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("message"), "3 records were deleted")

        # Test project details updated successfully
        self.assertEqual(
            self.xform.project.date_modified.strftime("%Y-%m-%d %H:%M:%S"),
            timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # Test XForm now contains no submissions
        self.xform.refresh_from_db()
        delete_all_current_count = self.xform.instances.filter(deleted_at=None).count()
        self.assertNotEqual(current_count, delete_all_current_count)
        self.assertEqual(delete_all_current_count, 0)
        self.assertEqual(self.xform.num_of_submissions, 0)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    def test_delete_submission_by_editor(self, send_message_mock):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by("id")[0].pk
        view = DataViewSet.as_view({"delete": "destroy", "get": "list"})

        # 4 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        self._create_user_and_login(username="alice", password="alice")

        # Editor can delete submission
        role.EditorRole.add(self.user, self.xform)
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        request = self.factory.delete("/", **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None).order_by("id")[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)
        self.assertTrue(send_message_mock.called)

    @patch("onadata.apps.api.viewsets.data_viewset.send_message")
    def test_delete_submission_by_owner(self, send_message_mock):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by("id")[0].pk
        view = DataViewSet.as_view({"delete": "destroy", "get": "list"})

        # 4 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        self._create_user_and_login(username="alice", password="alice")

        # Owner can delete submission
        role.OwnerRole.add(self.user, self.xform)
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        request = self.factory.delete("/", **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None).order_by("id")[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)
        self.assertTrue(send_message_mock.called)

    def test_geojson_pagination(self):
        self._publish_submit_geojson()

        # test geojson response before pagination

        data_get = {
            "fields": "today",
        }

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")
        instances = self.xform.instances.all().order_by("id")
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[0].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[1].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[2].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[3].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
            ],
        }
        self.assertEqual(response.status_code, 200)
        # test that all 4 geojson features are returned
        self.assertEqual(len(response.data.get("features")), 4)
        self.assertEqual(response.data, data)

        # test geojson response when pagination params are applied
        data_get = {"fields": "today", "page": 1, "page_size": 2}

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")
        instances = self.xform.instances.all().order_by("id")
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[0].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[1].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
            ],
        }
        self.assertEqual(response.status_code, 200)
        # test that only 2 features are returned based on page size
        self.assertEqual(len(response.data.get("features")), 2)
        self.assertEqual(response.data, data)

    def test_geojson_format(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by("id")[0].pk

        view = DataViewSet.as_view({"get": "retrieve"})
        data_get = {"fields": "today"}
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid, format="geojson")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.xform.instances.count(), 4)

        test_geo = {
            "type": "Feature",
            "geometry": {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": "Point", "coordinates": [36.787219, -1.294197]}
                ],
            },
            "properties": {"id": dataid, "xform": self.xform.pk, "today": "2015-01-15"},
        }

        self.assertEqual(response.data, test_geo)

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")
        instances = self.xform.instances.all().order_by("id")
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[0].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[1].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[2].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "coordinates": [36.787219, -1.294197]}
                        ],
                    },
                    "properties": {
                        "id": instances[3].pk,
                        "xform": self.xform.pk,
                        "today": "2015-01-15",
                    },
                },
            ],
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    @patch("onadata.apps.api.viewsets.data_viewset" ".DataViewSet.paginate_queryset")
    def test_retry_on_operational_error(self, mock_paginate_queryset):
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        mock_paginate_queryset.side_effect = [
            OperationalError,
            Instance.objects.filter(xform_id=formid)[:2],
        ]

        request = self.factory.get(
            "/", data={"page": "1", "page_size": 2}, **self.extra
        )
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_paginate_queryset.call_count, 2)

    def test_geojson_simple_style(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by("id")[0].pk

        data_get = {"geo_field": "location", "simple_style": "true"}

        view = DataViewSet.as_view({"get": "retrieve"})

        request = self.factory.get("/", data=data_get, **self.extra)

        response = view(request, pk=self.xform.pk, dataid=dataid, format="geojson")

        self.assertEqual(response.status_code, 200)
        # build out geojson simple style spec
        test_loc = geojson.Feature(
            geometry=geojson.Point((36.787219, -1.294197)),
            properties={"xform": self.xform.pk, "id": dataid},
        )
        if "id" in test_loc:
            test_loc.pop("id")

        self.assertEqual(response.data, test_loc)

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")
        self.assertEqual(len(response.data["features"]), 4)
        self.assertEqual(response.data["features"][0]["type"], "Feature")
        self.assertEqual(response.data["features"][0]["geometry"]["type"], "Point")

    def test_geojson_simple_style_title_prop(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by("id")[0].pk

        data_get = {
            "geo_field": "location",
            "simple_style": "true",
            "title": "location",
        }

        view = DataViewSet.as_view({"get": "retrieve"})

        request = self.factory.get("/", data=data_get, **self.extra)

        response = view(request, pk=self.xform.pk, dataid=dataid, format="geojson")

        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.data["properties"])
        self.assertEqual(
            "-1.294197 36.787219 0 34", response.data["properties"]["title"]
        )

    def test_geojson_geofield(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by("id")[0].pk

        data_get = {"geo_field": "location", "fields": "today"}

        view = DataViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid, format="geojson")

        self.assertEqual(response.status_code, 200)
        test_loc = geojson.Feature(
            geometry=geojson.GeometryCollection(
                [geojson.Point((36.787219, -1.294197))]
            ),
            properties={"xform": self.xform.pk, "id": dataid, "today": "2015-01-15"},
        )
        if "id" in test_loc:
            test_loc.pop("id")

        self.assertEqual(response.data, test_loc)

        view = DataViewSet.as_view({"get": "list"})

        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")
        self.assertEqual(len(response.data["features"]), 4)
        self.assertEqual(response.data["features"][0]["type"], "Feature")
        self.assertEqual(
            response.data["features"][0]["geometry"]["geometries"][0]["type"], "Point"
        )

    def test_geojson_linestring(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by("id")[0].pk

        data_get = {"geo_field": "path", "fields": "today,path"}

        view = DataViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid, format="geojson")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["type"], "Feature")
        self.assertEqual(len(response.data["geometry"]["coordinates"]), 5)
        self.assertIn("path", response.data["properties"])
        self.assertEqual(response.data["geometry"]["type"], "LineString")

        view = DataViewSet.as_view({"get": "list"})

        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")
        self.assertEqual(len(response.data["features"]), 4)
        self.assertEqual(response.data["features"][0]["type"], "Feature")
        self.assertEqual(response.data["features"][0]["geometry"]["type"], "LineString")

    def test_geojson_polygon(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by("id")[0].pk

        data_get = {"geo_field": "shape", "fields": "today,shape"}

        view = DataViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid, format="geojson")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["type"], "Feature")
        self.assertEqual(len(response.data["geometry"]["coordinates"][0]), 6)
        self.assertIn("shape", response.data["properties"])
        self.assertEqual(response.data["geometry"]["type"], "Polygon")

        view = DataViewSet.as_view({"get": "list"})

        request = self.factory.get("/", data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format="geojson")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")
        self.assertEqual(len(response.data["features"]), 4)
        self.assertEqual(response.data["features"][0]["type"], "Feature")
        self.assertEqual(response.data["features"][0]["geometry"]["type"], "Polygon")

    def test_data_in_public_project(self):
        self._make_submissions()

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        with HTTMock(enketo_urls_mock):
            response = view(request, pk=formid)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 4)
            # get project id
            projectid = self.xform.project.pk

            view = ProjectViewSet.as_view({"put": "update"})

            data = {
                "public": True,
                "name": "test project",
                "owner": "http://testserver/api/v1/users/%s" % self.user.username,
            }
            request = self.factory.put("/", data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 200)
            self.xform.refresh_from_db()
            self.assertEqual(self.xform.shared, True)

            # anonymous user
            view = DataViewSet.as_view({"get": "list"})
            request = self.factory.get("/")
            formid = self.xform.pk
            response = view(request, pk=formid)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 4)

    def test_data_diff_version(self):
        self._make_submissions()
        # update the form version
        self.xform.version = "212121211"
        self.xform.save()

        # make more submission after form update
        surveys = ["transport_2011-07-25_19-05-36-edited"]
        main_directory = os.path.dirname(main_tests.__file__)
        paths = [
            os.path.join(
                main_directory,
                "fixtures",
                "transportation",
                "instances_w_uuid",
                s,
                s + ".xml",
            )
            for s in surveys
        ]

        auth = DigestAuth("bob", "bob")
        for path in paths:
            self._make_submission(path, None, None, auth=auth)

        data_view = DataViewSet.as_view({"get": "list"})

        request = self.factory.get("/", **self.extra)

        response = data_view(request, pk=self.xform.pk)

        self.assertEqual(len(response.data), 5)

        query_str = '{"_version": "2014111"}'
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = data_view(request, pk=self.xform.pk)

        self.assertEqual(len(response.data), 4)

        query_str = '{"_version": "212121211"}'
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = data_view(request, pk=self.xform.pk)

        self.assertEqual(len(response.data), 1)

    def test_last_modified_on_data_list_response(self):
        self._make_submissions()

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Cache-Control"), "max-age=60")

        self.assertTrue(response.has_header("ETag"))
        etag_value = response.get("ETag")

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(etag_value, response.get("ETag"))

        # delete one submission
        inst = Instance.objects.filter(xform=self.xform)
        inst[0].delete()

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(etag_value, response.get("ETag"))

    def test_submission_history(self):
        """Test submission json includes has_history key"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
        )

        self._make_submission(xml_submission_file_path)
        instance = Instance.objects.last()
        instance_count = Instance.objects.count()
        instance_history_count = InstanceHistory.objects.count()

        # edit submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml",
        )
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml",
        )
        client = DigestClient()
        client.set_authorization("bob", "bob", "Digest")
        self._make_submission(xml_edit_submission_file_path, client=client)

        self.assertEqual(self.response.status_code, 201)

        self.assertEqual(instance_count, Instance.objects.count())
        self.assertEqual(instance_history_count + 1, InstanceHistory.objects.count())

        # retrieve submission history
        view = DataViewSet.as_view({"get": "history"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, dataid=instance.id)
        self.assertEqual(response.status_code, 200)

        history_instance = InstanceHistory.objects.last()
        instance = Instance.objects.last()

        self.assertDictEqual(response.data[0], history_instance.json)
        self.assertNotEqual(response.data[0], instance.json)

    def test_submission_history_not_digit(self):
        """Test submission json includes has_history key"""
        # retrieve submission history
        view = DataViewSet.as_view({"get": "history"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, dataid="boo!")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Data ID should be an integer")

        history_instance_count = InstanceHistory.objects.count()
        self.assertEqual(history_instance_count, 0)

    def test_data_endpoint_etag_on_submission_edit(self):
        """Test etags get updated on submission edit"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        def _data_response():
            view = DataViewSet.as_view({"get": "list"})
            request = self.factory.get("/", **self.extra)
            response = view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 200)

            return response

        response = _data_response()

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
        )

        self._make_submission(xml_submission_file_path)
        response = _data_response()
        etag_data = response["Etag"]

        # edit submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml",
        )
        client = DigestClient()
        client.set_authorization("bob", "bob", "Digest")
        self._make_submission(xml_edit_submission_file_path, client=client)
        self.assertEqual(self.response.status_code, 201)

        response = _data_response()
        self.assertNotEqual(etag_data, response["Etag"])
        etag_data = response["Etag"]
        response = _data_response()
        self.assertEqual(etag_data, response["Etag"])

    def test_submission_edit_w_blank_field(self):
        """Test submission json includes has_history key"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
        )

        self._make_submission(xml_submission_file_path)
        instance = Instance.objects.last()
        instance_count = Instance.objects.count()

        # edit submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited_blank.xml",
        )
        client = DigestClient()
        client.set_authorization("bob", "bob", "Digest")
        self._make_submission(xml_edit_submission_file_path, client=client)

        self.assertEqual(self.response.status_code, 201)

        self.assertEqual(instance_count, Instance.objects.count())

        # retrieve submission history
        view = DataViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, dataid=instance.id)

        self.assertEqual(instance_count, Instance.objects.count())
        self.assertNotIn("name", response.data)

    def test_filterset(self):
        # create submissions to test with
        self._make_submissions()
        formid = self.xform.pk
        # the original count of Instance objects
        instance_count = Instance.objects.all().count()
        # ## Test no filters
        request = self.factory.get("/", **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(len(response.data), instance_count)
        # ## Test version
        # all the instances created have no version
        # we now set one instance to have a specific version and then test
        # that we can filter for it
        instance = Instance.objects.last()
        instance.version = 777
        instance.save()
        request = self.factory.get("/", {"version": 777}, **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data), Instance.objects.filter(version=777).count()
        )
        # ## Test Status
        # all the instanced created have the same status i.e.
        # 'submitted_via_web' .  We now set one instance to have a different
        # status and filter for it
        instance = Instance.objects.last()
        instance.status = "fortytwo"
        instance.save()
        request = self.factory.get("/", {"status": "fortytwo"}, **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data), Instance.objects.filter(status="fortytwo").count()
        )
        # ## Test date_created
        # all the instances created have the same date_created i.e. the
        # datetime at the time of creation
        # we now set one instance to have date_created a year ago and test that
        # we can filter for this one instance
        one_year = timedelta(days=366)
        initial_year = instance.date_created.year
        instance.date_created = instance.date_created - one_year
        instance.save()
        request = self.factory.get(
            "/", {"date_created__year__lt": initial_year}, **self.extra
        )
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data),
            Instance.objects.filter(date_created__year__lt=initial_year).count(),
        )
        # ## Test last_edited
        # all the instances created have None as the last_edited
        # we now set one instance to have last_edited a year ago and test that
        # we can filter for this one instance
        instance.last_edited = instance.date_created - one_year
        instance.save()
        request = self.factory.get(
            "/", {"last_edited__year": initial_year}, **self.extra
        )
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data),
            Instance.objects.filter(last_edited__year=initial_year).count(),
        )
        # ## Test uuid
        # all the instances created have different uuid values
        # we test this by looking for just one match
        request = self.factory.get("/", {"uuid": instance.uuid}, **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data), Instance.objects.filter(uuid=instance.uuid).count()
        )
        # ## Test user
        # all the forms are owned by a user named bob
        # we create a user named alice and confirm that data filtered for her
        # has a count fo 0
        user_alice = self._create_user("alice", "alice")
        request = self.factory.get("/", {"user__id": user_alice.id}, **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(len(response.data), 0)
        # we make one instance belong to user_alice and then filter for that
        instance.user = user_alice
        instance.save()
        request = self.factory.get(
            "/", {"user__username": user_alice.username}, **self.extra
        )
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data),
            Instance.objects.filter(user__username=user_alice.username).count(),
        )
        # ## Test submitted_by
        # submitted_by is mapped to the user field
        # to test, we do the same as we did for user above
        user_mosh = self._create_user("mosh", "mosh")
        request = self.factory.get(
            "/", {"submitted_by__id": user_mosh.id}, **self.extra
        )
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(len(response.data), 0)
        # we make one instance belong to user_mosh and then filter for that
        instance.user = user_mosh
        instance.save()
        request = self.factory.get(
            "/", {"submitted_by__username": user_mosh.username}, **self.extra
        )
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data),
            Instance.objects.filter(user__username=user_mosh.username).count(),
        )
        #  ## Test survey_type
        # all the instances created have the same survey_type
        # we create a new one and filter for that
        new_survey_type = SurveyType.objects.create(slug="hunter2")
        instance.survey_type = new_survey_type
        instance.save()
        request = self.factory.get(
            "/", {"survey_type__slug": new_survey_type.slug}, **self.extra
        )
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(
            len(response.data),
            Instance.objects.filter(survey_type__slug=new_survey_type.slug).count(),
        )
        # ## Test all_media_received
        # all the instances have media_all_received == True
        request = self.factory.get("/", {"media_all_received": "false"}, **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(len(response.data), 1)
        # we set one to False and filter for it
        instance.media_all_received = False
        instance.save()
        request = self.factory.get("/", {"media_all_received": "false"}, **self.extra)
        view = DataViewSet.as_view({"get": "list"})
        response = view(request, pk=formid, format="json")
        self.assertEqual(len(response.data), 2)

    def test_floip_format(self):
        """
        Test FLOIP output results.
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk
        request = self.factory.get(
            "/",
            HTTP_ACCEPT="application/vnd.org.flowinterop.results+json",
            **self.extra,
        )
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        response.render()
        floip_list = json.loads(response.content)
        self.assertTrue(isinstance(floip_list, list))
        floip_row = [x for x in floip_list if x[-2] == "none"][0]
        self.assertEqual(floip_row[0], response.data[0]["_submission_time"] + "+00:00")
        self.assertEqual(floip_row[2], "bob")
        self.assertEqual(floip_row[3], response.data[0]["_uuid"])
        self.assertEqual(
            floip_row[4],
            "transport/available_transportation_types_to_referral_facility",
        )
        self.assertEqual(floip_row[5], "none")

    def test_submission_count_for_day_tracking(self):
        """
        Test that the submission_count_for_today value is accurately tracked
        """
        # Ensure cache is cleared
        cache.clear()
        # Ensure that new submissions are added into the count
        self._make_submissions()
        form = self.xform
        c_date = datetime.datetime.today()
        instances = Instance.objects.filter(date_created__date=c_date.date())
        current_count = instances.count()
        self.assertEqual(form.submission_count_for_today, current_count)

        # Confirm that the submission count is decreased
        # accordingly
        inst_one = instances[0]
        inst_two = instances[1]
        inst_three = instances[2]

        inst_one.set_deleted()
        current_count -= 1
        self.assertEqual(form.submission_count_for_today, current_count)

        # Confirm submission count isn't decreased if the
        # date_created is different
        future_date = c_date - timedelta(days=1)
        inst_two.date_created = future_date
        inst_two.save()
        inst_two.set_deleted()
        self.assertEqual(form.submission_count_for_today, current_count)

        # Check that deletes made with no current count cached
        # are successful
        cache.clear()
        inst_three.set_deleted()

    def test_data_query_multiple_condition(self):
        """
        Test that all conditions are met when a user queries for
        data
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        query_str = (
            '{"$or":[{"transport/loop_over_transport_types_frequency'
            '/ambulance/frequency_to_referral_facility":"weekly","t'
            "ransport/loop_over_transport_types_frequency/ambulanc"
            'e/frequency_to_referral_facility":"daily"}]}'
        )
        request = self.factory.get(f"/?query={query_str}", **self.extra)
        response = view(request, pk=self.xform.pk)
        count = 0

        for inst in self.xform.instances.all():
            if inst.json.get(
                "transport/loop_over_transport_types_frequency"
                "/ambulance/frequency_to_referral_facility"
            ) in ["daily", "weekly"]:
                count += 1

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), count)

        query_str = (
            '{"$or":[{"transport/loop_over_transport_types_frequency'
            '/ambulance/frequency_to_referral_facility":"weekly"}, {"t'
            "ransport/loop_over_transport_types_frequency/ambulanc"
            'e/frequency_to_referral_facility":"daily"}]}'
        )
        request = self.factory.get(f"/?query={query_str}", **self.extra)
        response = view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), count)

    def test_data_query_ornull(self):
        """
        Test that a user is able to query for null with the
        $or filter option
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        query_str = '{"$or": [{"_review_status":"3"}' ', {"_review_status": null }]}'
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        instances = self.xform.instances.all().order_by("pk")
        instance = instances[0]
        self.assertFalse(instance.has_a_review)

        # Review instance
        data = {"instance": instance.id, "status": SubmissionReview.APPROVED}

        serializer_instance = SubmissionReviewSerializer(
            data=data, context={"request": request}
        )
        serializer_instance.is_valid()
        serializer_instance.save()
        instance.refresh_from_db()

        # Assert that the approved instance is no longer returned
        # when querying
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        # Switch review to pending
        data = {"instance": instance.id, "status": SubmissionReview.PENDING}

        serializer_instance = SubmissionReviewSerializer(
            data=data, context={"request": request}
        )
        serializer_instance.is_valid()
        serializer_instance.save()
        instance.refresh_from_db()

        # Assert instance is now a part of the values when querying
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        instance = instances[1]
        # Switch review to Rejected
        data = {
            "instance": instance.id,
            "status": SubmissionReview.REJECTED,
            "note": "Testing",
        }

        serializer_instance = SubmissionReviewSerializer(
            data=data, context={"request": request}
        )
        serializer_instance.is_valid()
        serializer_instance.save()
        instance.refresh_from_db()

        # Assert ornull operator still works with multiple values
        query_str = (
            '{"$or": [{"_review_status":"3"},'
            ' {"_review_status": "2"}, {"_review_status": null}]}'
        )
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_list_xml_format(self):
        """Test DataViewSet list XML"""
        # create submission
        media_file = "1335783522563.jpg"
        self._make_submission_w_attachment(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                "transport_2011-07-25_19-05-49_2",
                "transport_2011-07-25_19-05-49_2.xml",
            ),
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                "transport_2011-07-25_19-05-49_2",
                media_file,
            ),
        )

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid, format="xml")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

        # Ensure response is renderable
        response.render()
        self.assertEqual(response.accepted_media_type, "application/xml")
        instance = self.xform.instances.first()
        returned_xml = response.content.decode("utf-8")
        server_time = ET.fromstring(returned_xml).attrib.get("serverTime")
        edited = instance.last_edited is not None
        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        attachment = instance.attachments.first()
        expected_xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<submission-batch serverTime="{server_time}">'  # noqa
            f'<submission-item bambooDatasetId="" dateCreated="{instance.date_created.isoformat()}" duration="" edited="{edited}" formVersion="{instance.version}"'  # noqa
            f' lastModified="{instance.date_modified.isoformat()}" mediaAllReceived="{instance.media_all_received}" mediaCount="{ instance.media_count }" objectID="{instance.id}" reviewComment="" reviewStatus=""'  # noqa
            f' status="{instance.status}" submissionTime="{submission_time}" submittedBy="{instance.user.username}" totalMedia="{ instance.total_media }">'  # noqa
            f'<transportation id="{instance.xform.id_string}" version="{instance.version}">'  # noqa
            "<transport>"
            "<available_transportation_types_to_referral_facility>none</available_transportation_types_to_referral_facility>"  # noqa
            "<loop_over_transport_types_frequency><ambulance></ambulance><bicycle></bicycle><boat_canoe></boat_canoe><bus></bus><donkey_mule_cart></donkey_mule_cart><keke_pepe></keke_pepe><lorry></lorry><motorbike></motorbike><taxi></taxi><other></other></loop_over_transport_types_frequency>"  # noqa
            "</transport>"
            '<image1 type="file">1335783522563.jpg</image1>'
            "<meta><instanceID>uuid:5b2cc313-fc09-437e-8149-fcd32f695d41</instanceID></meta>"  # noqa
            "</transportation>"
            "<linked-resources>"
            "<attachments>"
            f"<id>{attachment.id}</id><name>1335783522563.jpg</name><xform>{instance.xform.id}</xform><filename>{ attachment.media_file.name }</filename><instance>{ instance.id }</instance><mimetype>image/jpeg</mimetype><download_url>/api/v1/files/{attachment.id}?filename={ attachment.media_file.name }</download_url><small_download_url>/api/v1/files/{attachment.id}?filename={ attachment.media_file.name }&amp;suffix=small</small_download_url><medium_download_url>/api/v1/files/{attachment.id}?filename={ attachment.media_file.name }&amp;suffix=medium</medium_download_url></attachments>"  # noqa
            "</linked-resources>"
            "</submission-item>"
            "</submission-batch>"
        )
        self.assertEqual(expected_xml, returned_xml)

    def test_invalid_xml_elements_not_present(self):
        """
        Test invalid XML elements such as #text are not present in XML Response
        """
        self._make_submission(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                "transport_2011-07-25_19-05-49_2",
                "transport_2011-07-25_19-05-49_2.xml",
            )
        )
        media_file = "1335783522563.jpg"
        self._make_submission_w_attachment(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                "transport_2011-07-25_19-05-49_2",
                "transport_2011-07-25_19-05-49_2.xml",
            ),
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                "transport_2011-07-25_19-05-49_2",
                media_file,
            ),
        )

        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.xform.pk, format="xml")
        self.assertEqual(response.status_code, 200)

        # Ensure XML is well formed
        response.render()
        returned_xml = response.content.decode("utf-8")
        ET.fromstring(returned_xml)

    @override_settings(STREAM_DATA=True)
    def test_data_list_xml_format_no_data(self):
        """Test DataViewSet Query list XML"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/forms/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        view = DataViewSet.as_view({"get": "list"})

        formid = self.xform.pk
        query_str = '{"_date_modified":{"$gt":"2020-01-22T11:42:20"}}'
        request = self.factory.get("/?query=%s" % query_str, **self.extra)
        response = view(request, pk=formid, format="xml")

        self.assertEqual(response.status_code, 200)

        returned_xml = "".join([i.decode("utf-8") for i in response.streaming_content])

        server_time = ET.fromstring(returned_xml).attrib.get("serverTime")

        expected_xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<submission-batch serverTime="{server_time}">'
            "</submission-batch>"
        )

        self.assertEqual(expected_xml, returned_xml)

    def test_data_list_xml_format_sort(self):
        """
        Test that "sort" query param works as expected on XML formatted
        responses
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        formid = self.xform.pk

        expected_order = list(
            Instance.objects.filter(xform=self.xform)
            .order_by("-date_modified")
            .values_list("id", flat=True)
        )
        request = self.factory.get("/?sort=-_date_modified", **self.extra)
        response = view(request, pk=formid, format="xml")
        self.assertEqual(response.status_code, 200)
        items_in_order = [int(data.get("@objectID")) for data in response.data]
        self.assertEqual(expected_order, items_in_order)

        # Test `last_edited` field is sorted correctly
        expected_order = list(
            Instance.objects.filter(xform=self.xform)
            .order_by("last_edited")
            .values_list("id", flat=True)
        )
        request = self.factory.get("/?sort=_last_edited", **self.extra)
        response = view(request, pk=formid, format="xml")
        self.assertEqual(response.status_code, 200)
        items_in_order = [int(data.get("@objectID")) for data in response.data]
        self.assertEqual(expected_order, items_in_order)

    @override_settings(SUBMISSION_RETRIEVAL_THRESHOLD=1)
    def test_data_paginated_past_threshold(self):
        """
        Test that the data viewset paginates responses by default when
        the requested data surpasses the SUBMISSION_RETRIEVAL_THRESHOLD
        """
        self._make_submissions()
        view = DataViewSet.as_view({"get": "list"})
        request = self.factory.get("/", **self.extra)
        formid = self.xform.pk
        count = self.xform.instances.all().count()
        self.assertTrue(count > 1)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertIn("Link", response)
        self.assertEqual(
            response["Link"],
            '<http://testserver/?page=2&page_size=1>; rel="next", '
            '<http://testserver/?page=4&page_size=1>; rel="last"',
        )


class TestOSM(TestAbstractViewSet):
    """
    Test OSM endpoints in data_viewset.
    """

    def setUp(self):
        super().setUp()
        self._login_user_and_profile()
        self.factory = RequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        self.logger = logging.getLogger("console_logger")

    # pylint: disable=invalid-name,too-many-locals
    @flaky(max_runs=5)
    def test_data_retrieve_instance_osm_format(self):
        """Test /data endpoint OSM format."""
        filenames = [
            "OSMWay234134797.osm",
            "OSMWay34298972.osm",
        ]
        osm_fixtures_dir = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "fixtures", "osm")
        )
        paths = [os.path.join(osm_fixtures_dir, filename) for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, "osm.xlsx")
        combined_osm_path = os.path.join(osm_fixtures_dir, "combined.osm")
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, "instance_a.xml")
        files = [open(path, "rb") for path in paths]
        self._make_submission(submission_path, media_file=files)
        self.assertTrue(hasattr(self, "instance"))
        self.assertEqual(self.instance.attachments.all().count(), len(files))

        formid = self.instance.xform.pk
        dataid = self.instance.pk
        request = self.factory.get("/", **self.extra)

        # look at the data/[pk]/[dataid].osm endpoint
        view = DataViewSet.as_view({"get": "list"})
        response1 = view(request, pk=formid, format="osm")
        self.assertEqual(response1.status_code, 200)

        # look at the data/[pk]/[dataid].osm endpoint
        view = DataViewSet.as_view({"get": "retrieve"})
        response = view(request, pk=formid, dataid=dataid, format="osm")
        self.assertEqual(response.status_code, 200)
        with open(combined_osm_path, encoding="utf-8") as f:
            osm = f.read()
            response.render()
            self.assertMultiLineEqual(
                response.content.decode("utf-8").strip(), osm.strip()
            )

            # look at the data/[pk].osm endpoint
            view = DataViewSet.as_view({"get": "list"})
            response = view(request, pk=formid, format="osm")
            self.assertEqual(response.status_code, 200)
            response.render()
            response1.render()
            self.assertMultiLineEqual(
                response1.content.decode("utf-8").strip(), osm.strip()
            )
            self.assertMultiLineEqual(
                response.content.decode("utf-8").strip(), osm.strip()
            )

        # filter using value that exists
        request = self.factory.get(
            "/", data={"query": '{"osm_road": "OSMWay234134797.osm"}'}, **self.extra
        )
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 1)

        # filter using value that doesn't exists
        request = self.factory.get(
            "/", data={"query": '{"osm_road": "OSMWay123456789.osm"}'}, **self.extra
        )
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 0)
