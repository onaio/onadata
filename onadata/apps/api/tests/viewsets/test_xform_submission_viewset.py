# -*- coding: utf-8 -*-
"""
Test XFormSubmissionViewSet module.
"""

import os
from builtins import open  # pylint: disable=redefined-builtin
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import UnreadablePostError
from django.test import TransactionTestCase, override_settings
from django.urls.exceptions import NoReverseMatch
from django.utils import timezone

import simplejson as json
from django_digest.test import DigestAuth
from rest_framework import status
from rest_framework.reverse import reverse

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet,
    add_uuid_to_submission_xml,
)
from onadata.apps.api.viewsets.xform_submission_viewset import XFormSubmissionViewSet
from onadata.apps.logger.models import Attachment, Instance, KMSKey, XForm
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.services.textit import ServiceDefinition
from onadata.libs.permissions import DataEntryRole
from onadata.libs.utils.common_tools import get_uuid


# pylint: disable=W0201,R0904,C0103
class TestXFormSubmissionViewSet(TestAbstractViewSet, TransactionTestCase):
    """
    TestXFormSubmissionViewSet test class.
    """

    def setUp(self):
        super(TestXFormSubmissionViewSet, self).setUp()
        self.view = XFormSubmissionViewSet.as_view({"head": "create", "post": "create"})
        self._publish_xls_form_to_project()

    def test_unique_instanceid_per_form_only(self):
        """
        Test unique instanceID submissions per form.
        """
        self._make_submissions()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice = self._create_user_profile(alice_data)
        self.user = alice.user
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % self.user.auth_token}
        self._publish_xls_form_to_project()
        self._make_submissions()

    def test_post_submission_anonymous(self):
        """
        Test anonymous user can make a submission.
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/%s/submission" % self.user.username, data)
                request.user = AnonymousUser()
                response = self.view(request, username=self.user.username)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    "http://testserver/%s/submission" % self.user.username,
                )

    def test_username_case_insensitive(self):
        """
        Test that the form owners username is matched without regards
        to the username case
        """
        # Change username to Bob
        self.user.username = "Bob"
        self.user.save()

        survey = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            media_file,
        )
        form = XForm.objects.get(user=self.user)
        count = form.submission_count()
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                survey,
                survey + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                # Make submission to /bob/submission
                request = self.factory.post("/%s/submission" % "bob", data)
                request.user = AnonymousUser()
                response = self.view(request, username=self.user.username)

                # Submission should be submitted to the right form
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(count + 1, form.submission_count())

    def test_post_submission_authenticated(self):
        """
        Test authenticated user can make a submission.
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_submission_uuid_other_user_username_not_provided(self):
        """
        Test submission without formhub/uuid done by a different user who has
        no permission to the form fails.
        """
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._create_user_profile(alice_data)
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            path = add_uuid_to_submission_xml(path, self.xform)

            with open(path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("alice", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request)
                self.assertEqual(response.status_code, 404)

    def test_post_submission_uuid_duplicate_no_username_provided(self):
        """
        Test submission to a duplicate of a form with a different uuid
        from the original is properly routed to the request users version of
        the form
        """
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            path = add_uuid_to_submission_xml(path, self.xform)

            with open(path, "rb") as sf:
                # Submits to the correct form
                count = XForm.objects.count()
                original_form_pk = self.xform.pk
                duplicate_form = self.xform
                duplicate_form.pk = None
                duplicate_form.uuid = get_uuid()
                duplicate_form.user = alice_profile.user
                duplicate_form.save()
                duplicate_form.refresh_from_db()

                self.assertNotEqual(original_form_pk, duplicate_form.pk)
                self.assertEqual(XForm.objects.count(), count + 1)

                request = self.factory.post(
                    "/submission", {"xml_submission_file": sf, "media_file": f}
                )
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("alice", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request)
                self.assertEqual(response.status_code, 201)
                duplicate_form.refresh_from_db()
                self.assertEqual(duplicate_form.instances.all().count(), 1)
                self.assertEqual(
                    XForm.objects.get(pk=original_form_pk).instances.all().count(), 0
                )

    def test_post_submission_authenticated_json(self):
        """
        Test authenticated user can make a JSON submission.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "transport_submission.json",
        )
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read())
            request = self.factory.post("/submission", data, format="json")
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, "Successful submission", status_code=201)
            self.assertTrue(response.has_header("X-OpenRosa-Version"))
            self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
            self.assertTrue(response.has_header("Date"))
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_submission_authenticated_bad_json_list(self):
        """
        Test authenticated user cannot make a badly formatted JSON list
        submision.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "transport_submission.json",
        )
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read())
            request = self.factory.post("/submission", [data], format="json")
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, "Invalid data", status_code=400)
            self.assertTrue(response.has_header("X-OpenRosa-Version"))
            self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
            self.assertTrue(response.has_header("Date"))
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_submission_authenticated_bad_json_submission_list(self):
        """
        Test authenticated user cannot make a badly formatted JSON submission
        list.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "transport_submission.json",
        )
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read())
            data["submission"] = [data["submission"]]
            request = self.factory.post("/submission", data, format="json")
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, "Incorrect format", status_code=400)
            self.assertTrue(response.has_header("X-OpenRosa-Version"))
            self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
            self.assertTrue(response.has_header("Date"))
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_submission_authenticated_bad_json(self):
        """
        Test authenticated user cannot make a badly formatted JSON submission.
        """
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "fixtures",
            "transport_submission_bad.json",
        )
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read())
            request = self.factory.post("/submission", data, format="json")
            response = self.view(request)
            self.assertEqual(response.status_code, 401)

            request = self.factory.post("/submission", data, format="json")
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request)
            self.assertContains(response, "Received empty submission", status_code=400)
            self.assertTrue(response.has_header("X-OpenRosa-Version"))
            self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
            self.assertTrue(response.has_header("Date"))
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_submission_require_auth(self):
        """
        Test require_auth on submission post.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()
        submission = self.surveys[0]
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            submission,
            submission + ".xml",
        )
        with open(submission_path, "rb") as submission_file:
            data = {"xml_submission_file": submission_file}
            request = self.factory.post("/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            response = self.view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)
            self.assertContains(response, "Successful submission", status_code=201)
            self.assertTrue(response.has_header("X-OpenRosa-Version"))
            self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
            self.assertTrue(response.has_header("Date"))
            self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
            self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_submission_require_auth_anonymous_user(self):
        """
        Test anonymous user cannot make a submission if the form requires
        authentication.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()
        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                response = self.view(request, username=self.user.username)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(count, Attachment.objects.count())

    def test_post_submission_require_auth_other_user(self):
        """
        Test another authenticated user without permission to the form cannot
        make a submission if the form requires authentication.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._create_user_profile(alice_data)

        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                response = self.view(request, username=self.user.username)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(count, Attachment.objects.count())
                auth = DigestAuth("alice", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(
                    response,
                    "alice is not allowed to make submissions to bob",
                    status_code=403,
                )

    def test_post_submission_require_auth_data_entry_role(self):
        """
        Test authenticated user with the DataEntryRole role can make
        submissions to a form with require_auth = True.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        DataEntryRole.add(alice_profile.user, self.xform)

        count = Attachment.objects.count()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                response = self.view(request, username=self.user.username)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(count, Attachment.objects.count())
                auth = DigestAuth("alice", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(response, "Successful submission", status_code=201)

    def test_post_submission_json_without_submission_key(self):
        """
        Tesut JSON submission without the submission key fails.
        """
        data = {"id": "transportation_2011_07_25"}
        request = self.factory.post("/submission", data, format="json")
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertContains(response, "No submission key provided.", status_code=400)

    def test_NaN_in_submission(self):
        """
        Test submissions with uuid as NaN are successful.
        """
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
        )

        self._publish_xls_form_to_project(xlsform_path=xlsform_path)

        path = os.path.join(
            settings.PROJECT_ROOT,
            "libs",
            "tests",
            "utils",
            "fixtures",
            "tutorial",
            "instances",
            "uuid_NaN",
            "submission.xml",
        )
        self._make_submission(path)

    def test_rapidpro_post_submission(self):
        """
        Test a Rapidpro Webhook POST submission.
        """
        # pylint: disable=C0301
        data = json.dumps(
            {
                "contact": {
                    "name": "Davis",
                    "urn": "tel:+12065551212",
                    "uuid": "23dae14f-7202-4ff5-bdb6-2390d2769968",
                },
                "flow": {
                    "name": "1166",
                    "uuid": "9da5e439-35af-4ecb-b7fc-2911659f6b04",
                },
                "results": {
                    "fruit_name": {"category": "All Responses", "value": "orange"},
                },
            }
        )

        request = self.factory.post(
            "/submission",
            data,
            content_type="application/json",
            HTTP_USER_AGENT="RapidProMailroom/5.2.0",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertContains(response, "Successful submission", status_code=201)
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Location"], "http://testserver/submission")
        # InstanceID is returned as uuid:<uuid>.
        # Retrieving the uuid without the prefix in order to retrieve
        # the Instance object
        uuid = response.data.get("instanceID").split(":")[1]
        instance = Instance.objects.get(uuid=uuid)
        expected_xml = (
            f"<?xml version='1.0' ?><{self.xform.survey.name} id="
            "'transportation_2011_07_25'><fruit_name>orange"
            f"</fruit_name>\n<meta>\n  <instanceID>uuid:{uuid}"
            f"</instanceID>\n</meta></{self.xform.survey.name}>"
        )
        self.assertEqual(instance.xml, expected_xml)
        self.assertEqual(self.xform.survey.name, "data")

    def test_legacy_rapidpro_post_submission(self):
        """
        Test a Legacy Rapidpro Webhook POST submission.
        """
        # pylint: disable=C0301
        data = "run=76250&text=orange&flow_uuid=9da5e439-35af-4ecb-b7fc-2911659f6b04&phone=%2B12065550100&step=3b15df81-a0bd-4de7-8186-145ea3bb6c43&contact_name=Antonate+Maritim&flow_name=fruit&header=Authorization&urn=tel%3A%2B12065550100&flow=1166&relayer=-1&contact=fe4df540-39c1-4647-b4bc-1c93833e22e0&values=%5B%7B%22category%22%3A+%7B%22base%22%3A+%22All+Responses%22%7D%2C+%22node%22%3A+%228037c12f-a277-4255-b630-6a03b035767a%22%2C+%22time%22%3A+%222017-10-04T07%3A18%3A08.171069Z%22%2C+%22text%22%3A+%22orange%22%2C+%22rule_value%22%3A+%22orange%22%2C+%22value%22%3A+%22orange%22%2C+%22label%22%3A+%22fruit_name%22%7D%5D&time=2017-10-04T07%3A18%3A08.205524Z&steps=%5B%7B%22node%22%3A+%220e18202f-9ec4-4756-b15b-e9f152122250%22%2C+%22arrived_on%22%3A+%222017-10-04T07%3A15%3A17.548657Z%22%2C+%22left_on%22%3A+%222017-10-04T07%3A15%3A17.604668Z%22%2C+%22text%22%3A+%22Fruit%3F%22%2C+%22type%22%3A+%22A%22%2C+%22value%22%3A+null%7D%2C+%7B%22node%22%3A+%228037c12f-a277-4255-b630-6a03b035767a%22%2C+%22arrived_on%22%3A+%222017-10-04T07%3A15%3A17.604668Z%22%2C+%22left_on%22%3A+%222017-10-04T07%3A18%3A08.171069Z%22%2C+%22text%22%3A+%22orange%22%2C+%22type%22%3A+%22R%22%2C+%22value%22%3A+%22orange%22%7D%2C+%7B%22node%22%3A+%223b15df81-a0bd-4de7-8186-145ea3bb6c43%22%2C+%22arrived_on%22%3A+%222017-10-04T07%3A18%3A08.171069Z%22%2C+%22left_on%22%3A+null%2C+%22text%22%3A+null%2C+%22type%22%3A+%22A%22%2C+%22value%22%3A+null%7D%5D&flow_base_language=base&channel=-1"  # noqa
        request = self.factory.post(
            "/submission", data, content_type="application/x-www-form-urlencoded"
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertContains(response, "Successful submission", status_code=201)
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Location"], "http://testserver/submission")

    def test_post_empty_submission(self):
        """
        Test empty submission fails.
        """
        request = self.factory.post("/%s/submission" % self.user.username, {})
        request.user = AnonymousUser()
        response = self.view(request, username=self.user.username)
        self.assertContains(response, "No XML submission file.", status_code=400)

    def test_auth_submission_head_request(self):
        """
        Test HEAD submission request.
        """
        request = self.factory.head("/submission")
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Location"], "http://testserver/submission")

    def test_head_submission_anonymous(self):
        """
        Test HEAD submission request for anonymous user.
        """
        request = self.factory.head("/%s/submission" % self.user.username)
        request.user = AnonymousUser()
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(
            response["Location"], "http://testserver/%s/submission" % self.user.username
        )

    def test_floip_format_submission(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}]]'  # noqa
        request = self.factory.post(
            "/submission",
            data,
            content_type="application/vnd.org.flowinterop.results+json",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertContains(response, "Successful submission", status_code=201)
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Location"], "http://testserver/submission")

    def test_floip_format_submission_missing_column(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}]]'  # noqa
        request = self.factory.post(
            "/submission",
            data,
            content_type="application/vnd.org.flowinterop.results+json",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertContains(
            response,
            "Wrong number of values (5) in row 0, " "expecting 6 values",
            status_code=400,
        )

    def test_floip_format_submission_not_list(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '{"option_order": ["male", "female"]}'  # noqa
        request = self.factory.post(
            "/submission",
            data,
            content_type="application/vnd.org.flowinterop.results+json",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"non_field_errors": ["Invalid format. Expecting a list."]}
        )

    def test_floip_format_submission_is_valid_json(self):
        """
        Test receiving a row of FLOIP submission.
        """
        # pylint: disable=C0301
        data = '"2017-05-23T13:35:37.119-04:00", 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}'  # noqa
        request = self.factory.post(
            "/submission",
            data,
            content_type="application/vnd.org.flowinterop.results+json",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertContains(response, "Extra data", status_code=400)

    def test_floip_format_multiple_rows_submission(self):
        """
        Test FLOIP multiple rows submission
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}], ["2017-05-23T13:35:47.822-04:00", 20394823950, 923842093, "ae54d7", "chocolate", null ]]'  # noqa
        request = self.factory.post(
            "/submission",
            data,
            content_type="application/vnd.org.flowinterop.results+json",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        self.assertContains(response, "Successful submission", status_code=201)
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Location"], "http://testserver/submission")

    def test_floip_format_multiple_rows_instance(self):
        """
        Test data responses exist in instance values.
        """
        # pylint: disable=C0301
        data = '[["2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male", "female"]}], ["2017-05-23T13:35:47.822-04:00", 20394823950, 923842093, "ae54d7", "chocolate", null ]]'  # noqa
        request = self.factory.post(
            "/submission",
            data,
            content_type="application/vnd.org.flowinterop.results+json",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        response = self.view(
            request, username=self.user.username, xform_pk=self.xform.pk
        )
        instance_json = Instance.objects.last().json
        data_responses = [i[4] for i in json.loads(data)]
        self.assertTrue(any(i in data_responses for i in instance_json.values()))

    @patch(
        "onadata.apps.api.viewsets.xform_submission_viewset.SubmissionSerializer"
    )  # noqa
    def test_post_submission_unreadable_post_error(self, MockSerializer):
        """
        Test UnreadablePostError exception during submission..
        """
        MockSerializer.side_effect = UnreadablePostError()
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post("/%s/submission" % self.user.username, data)
                request.user = AnonymousUser()
                response = self.view(request, username=self.user.username)
                self.assertContains(
                    response, "Unable to read submitted file", status_code=400
                )
                self.assertTrue(response.has_header("X-OpenRosa-Version"))

    def test_post_submission_using_pk_while_anonymous(self):
        """
        Test that one is able to submit data using the enketo submission
        endpoint built for a particular form through it's primary key
        while anonymous
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(f"/enketo/{self.xform.pk}/submission", data)
                count = Instance.objects.filter(xform=self.xform).count()
                request.user = AnonymousUser()
                response = self.view(request, xform_pk=self.xform.pk)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/enketo/{self.xform.pk}/submission",
                )
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count + 1
                )

    def test_head_submission_request_w_no_auth(self):
        """
        Test enketo submission request with request method `HEAD`
        returns all headers when request is made with no auth provided.
        """
        # Enable requre_auth
        self.user.profile.require_auth = True
        self.user.profile.save()

        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb"):
                # When require_auth is enabled and
                # no auth is passed to the request should fail
                request = self.factory.head(f"/enketo/{self.xform.pk}/submission")
                response = self.view(request)
                self.assertEqual(response.status_code, 401)

                # When require_auth is enabled & no auth passed is ok
                request = self.factory.head(f"/enketo/{self.xform.pk}/submission")
                request.user = self.xform.user
                response = self.view(request, xform_pk=self.xform.pk)

                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))

                # Test Content-Length header is available
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/enketo/{self.xform.pk}/submission",
                )  # noqa

    def test_post_submission_using_pk_while_authenticated(self):
        """
        Test that one is able to submit data using the enketo
        submission endpoint built for a particular form through
        it's primary key while authenticated
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                count = Instance.objects.filter(xform=self.xform).count()
                request = self.factory.post(f"/enketo/{self.xform.pk}/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, form_pk=self.xform.pk)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/enketo/{self.xform.pk}/submission",
                )
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count + 1
                )

    def test_post_submission_using_form_pk_while_anonymous(self):
        """
        Test that one is able to submit data using the project submission
        endpoint built for a particular form through it's primary key
        while anonymous
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(f"/forms/{self.xform.pk}/submission", data)
                count = Instance.objects.filter(xform=self.xform).count()
                request.user = AnonymousUser()
                response = self.view(request, xform_pk=self.xform.pk)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/forms/{self.xform.pk}/submission",
                )
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count + 1
                )

    def test_post_submission_using_form_pk_while_authenticated(self):
        """
        Test that one is able to submit data using the forms
        submission endpoint built for a particular form through
        it's primary key while authenticated
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                count = Instance.objects.filter(xform=self.xform).count()
                request = self.factory.post(f"/forms/{self.xform.pk}/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, form_pk=self.xform.pk)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/forms/{self.xform.pk}/submission",
                )
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count + 1
                )

    def test_post_submission_using_project_pk_while_anonymous(self):
        """
        Test that one is able to submit data using the project submission
        endpoint built for a particular form through it's primary key
        while anonymous
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(
                    f"/projects/{self.xform.project.pk}/submission", data
                )
                count = Instance.objects.filter(xform=self.xform).count()
                request.user = AnonymousUser()
                response = self.view(request, xform_pk=self.xform.pk)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/projects/{self.xform.project.pk}/submission",
                )
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count + 1
                )

    def test_post_submission_using_project_pk_while_authenticated(self):
        """
        Test that one is able to submit data using the project
        submission endpoint built for a particular form through
        it's primary key while authenticated
        """
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                count = Instance.objects.filter(xform=self.xform).count()
                request = self.factory.post(
                    f"/projects/{self.xform.project.pk}/submission", data
                )
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, project_pk=self.project.pk)
                self.assertContains(response, "Successful submission", status_code=201)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/projects/{self.xform.project.pk}/submission",
                )
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count + 1
                )

    def test_submission_by_anon_w_username_w_require_auth_on(self):
        """Submission by anon user using username with require auth on is rejected"""
        # Turn on user's require auth
        self.user.profile.require_auth = True
        self.user.profile.save()

        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(f"/{self.user.username}/submission", data)
                request.user = AnonymousUser()
                response = self.view(request, username=self.user.username)

                self.assertContains(
                    response,
                    "Authentication credentials were not provided",
                    status_code=401,
                )
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/{self.user.username}/submission",
                )

    def test_submission_by_anon_w_form_pk_w_require_auth_on(self):
        """Submission by anon user using the xforms's pk with require auth on is rejected"""
        # Turn on forms's owner require auth
        owner_profile = self.xform.user.profile
        owner_profile.require_auth = True
        owner_profile.save()

        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(f"/forms/{self.xform.pk}/submission", data)
                request.user = AnonymousUser()
                response = self.view(request, xform_pk=self.xform.pk)

                self.assertContains(
                    response,
                    "Authentication credentials were not provided",
                    status_code=401,
                )
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/forms/{self.xform.pk}/submission",
                )

    def test_submission_by_anon_w_project_pk_w_require_auth_on(self):
        """Submission by anon user using the project's pk with require auth on is rejected"""
        # Turn on project's owner require auth
        owner_profile = self.project.organization.profile
        owner_profile.require_auth = True
        owner_profile.save()

        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(
                    f"/projects/{self.xform.project.pk}/submission", data
                )
                request.user = AnonymousUser()
                response = self.view(request, project_pk=self.project.pk)

                self.assertContains(
                    response,
                    "Authentication credentials were not provided",
                    status_code=401,
                )
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/projects/{self.xform.project.pk}/submission",
                )

    def test_project_creator_require_auth_status_ignored(self):
        """A project creator's require auth status is ignored

        If a different user other than the project's owner created the
        project, require auth status on their profile should not
        affect require auth status for the project
        """
        # Turn on project's owner require auth
        org_profile = self.project.organization.profile
        org_profile.require_auth = True
        org_profile.save()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        # Alice created the project, but Bob is the owner
        self.project.created_by = alice
        self.project.save()

        # Project creator's require auth is disabled
        self.assertFalse(alice_profile.require_auth)

        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                request = self.factory.post(
                    f"/projects/{self.xform.project.pk}/submission", data
                )
                request.user = AnonymousUser()
                response = self.view(request, project_pk=self.project.pk)
                # Submission by anonymous user is rejected because the project's
                # require auth status is determined by the owner's require auth
                # status and not the project's creator's require auth status
                self.assertContains(
                    response,
                    "Authentication credentials were not provided",
                    status_code=401,
                )
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
                self.assertEqual(
                    response["Location"],
                    f"http://testserver/projects/{self.xform.project.pk}/submission",
                )

    def test_post_submission_using_project_pk_exceptions(self):
        """
        Test that one is able to submit data using the project
        submission endpoint built for a particular form through
        it's primary key while authenticated
        """
        with self.assertRaises(NoReverseMatch):
            _url = reverse("submission", kwargs={"project_id": "mission"})
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )
        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )
            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}
                count = Instance.objects.filter(xform=self.xform).count()
                request = self.factory.post(
                    f"/projects/{self.xform.project.pk}hello/submission", data
                )
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, project_pk=f"{self.project.pk}hello")
                self.assertContains(response, "Invalid Project id.", status_code=400)
                self.assertTrue(response.has_header("X-OpenRosa-Version"))
                self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
                self.assertTrue(response.has_header("Date"))
                self.assertEqual(
                    Instance.objects.filter(xform=self.xform).count(), count
                )

    @patch.object(ServiceDefinition, "send")
    def test_new_submission_sent_to_rapidpro(self, mock_send):
        """Submission created is sent to RapidPro"""
        rest_service = RestService.objects.create(
            service_url="https://rapidpro.ona.io/api/v2/flow_starts.json",
            xform=self.xform,
            name="textit",
        )
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )

        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            )

            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}

                with self.captureOnCommitCallbacks(execute=True):
                    # Ensure on commit callbacks are executed
                    request = self.factory.post("/submission", data)
                    response = self.view(request)
                    self.assertEqual(response.status_code, 401)
                    auth = DigestAuth("bob", "bobbob")
                    request.META.update(auth(request.META, response))
                    response = self.view(request, username=self.user.username)

                self.assertContains(response, "Successful submission", status_code=201)
                instance = Instance.objects.all().order_by("-pk")[0]
                mock_send.assert_called_once_with(rest_service.service_url, instance)

    @patch.object(ServiceDefinition, "send")
    def test_edit_submission_sent_to_rapidpro(self, mock_send):
        """Submission edited is sent to RapidPro"""
        rest_service = RestService.objects.create(
            service_url="https://rapidpro.ona.io/api/v2/flow_starts.json",
            xform=self.xform,
            name="textit",
        )
        s = self.surveys[0]
        media_file = "1335783522563.jpg"
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            media_file,
        )

        with open(path, "rb") as f:
            f = InMemoryUploadedFile(
                f, "media_file", media_file, "image/jpg", os.path.getsize(path), None
            )
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                f"{s}_edited.xml",
            )

            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "media_file": f}

                with self.captureOnCommitCallbacks(execute=True):
                    # Ensure on commit callbacks are executed
                    request = self.factory.post("/submission", data)
                    response = self.view(request)
                    self.assertEqual(response.status_code, 401)
                    auth = DigestAuth("bob", "bobbob")
                    request.META.update(auth(request.META, response))
                    response = self.view(request, username=self.user.username)

                self.assertContains(response, "Successful submission", status_code=201)
                new_uuid = "6b2cc313-fc09-437e-8139-fcd32f695d41"
                instance = Instance.objects.get(uuid=new_uuid)
                mock_send.assert_called_once_with(rest_service.service_url, instance)

    @override_settings(KMS_KEY_NOT_FOUND_ACCEPT_SUBMISSION=False)
    def test_encryption_key_not_found_reject(self):
        """Submission is rejected if encryption key not found."""
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True  # Mark XForm as encrypted using managed keys
        self.xform.save()
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )

        with open(submission_xml_enc_path, "rb") as mf:
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances_encrypted",
                "submission.xml",
            )

            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "submission.xml.enc": mf}

                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(
                    response,
                    "Encryption key does not exist or is disabled.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

    @override_settings(KMS_KEY_NOT_FOUND_ACCEPT_SUBMISSION=False)
    def test_encryption_key_disabled_reject(self):
        """Submission is rejected if encryption key is disabled."""
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True  # Mark XForm as encrypted using managed keys
        self.xform.save()
        # Create KMSKey
        content_type = ContentType.objects.get_for_model(self.xform)
        kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=self.xform.pk,
            provider=KMSKey.KMSProvider.AWS,
            disabled_at=timezone.now(),  # Disable key
        )
        submission_version = "2025051326"
        self.xform.kms_keys.create(version=submission_version, kms_key=kms_key)
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )

        with open(submission_xml_enc_path, "rb") as mf:
            submission_path = os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances_encrypted",
                "submission.xml",
            )

            with open(submission_path, "rb") as sf:
                data = {"xml_submission_file": sf, "submission.xml.enc": mf}

                request = self.factory.post("/submission", data)
                response = self.view(request)
                self.assertEqual(response.status_code, 401)
                auth = DigestAuth("bob", "bobbob")
                request.META.update(auth(request.META, response))
                response = self.view(request, username=self.user.username)
                self.assertContains(
                    response,
                    "Encryption key does not exist or is disabled.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

    @override_settings(KMS_KEY_NOT_FOUND_ACCEPT_SUBMISSION=True)
    def test_encryption_key_not_found_accept(self):
        """Submission is accepted if encryption key not found."""
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True  # Mark XForm as encrypted using managed keys
        self.xform.save()
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(submission_xml_enc_path, "rb") as mf, open(
            submission_path, "rb"
        ) as sf:
            data = {"xml_submission_file": sf, "submission.xml.enc": mf}
            request = self.factory.post("/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(KMS_KEY_NOT_FOUND_ACCEPT_SUBMISSION=True)
    def test_encryption_key_disabled_accept(self):
        """Submission is accepted if encryption key is disabled."""
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True  # Mark XForm as encrypted using managed keys
        self.xform.save()
        # Create KMSKey
        content_type = ContentType.objects.get_for_model(self.xform)
        kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=self.xform.pk,
            provider=KMSKey.KMSProvider.AWS,
            disabled_at=timezone.now(),  # Disable key
        )
        submission_version = "2025051326"
        self.xform.kms_keys.create(version=submission_version, kms_key=kms_key)
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(submission_xml_enc_path, "rb") as mf, open(
            submission_path, "rb"
        ) as sf:
            data = {"xml_submission_file": sf, "submission.xml.enc": mf}
            request = self.factory.post("/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_encryption_key_not_found_default_setting(self):
        """Submission is accepted if encryption key not found and setting missing."""
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True  # Mark XForm as encrypted using managed keys
        self.xform.save()
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(submission_xml_enc_path, "rb") as mf, open(
            submission_path, "rb"
        ) as sf:
            data = {"xml_submission_file": sf, "submission.xml.enc": mf}
            request = self.factory.post("/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_encryption_key_disabled_default_setting(self):
        """Submission is accepted if encryption key is disabled and setting missing."""
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True  # Mark XForm as encrypted using managed keys
        self.xform.save()
        # Create KMSKey
        content_type = ContentType.objects.get_for_model(self.xform)
        kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=self.xform.pk,
            provider=KMSKey.KMSProvider.AWS,
            disabled_at=timezone.now(),  # Disable key
        )
        submission_version = "2025051326"
        self.xform.kms_keys.create(version=submission_version, kms_key=kms_key)
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(submission_xml_enc_path, "rb") as mf, open(
            submission_path, "rb"
        ) as sf:
            data = {"xml_submission_file": sf, "submission.xml.enc": mf}
            request = self.factory.post("/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_submission(self):
        """Submission is not duplicated if it already exists."""
        # Existing submission
        survey = self.surveys[0]
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            survey + ".xml",
        )
        self._make_submission(submission_path)
        self.assertEqual(Instance.objects.count(), 1)

        # Duplicate submission
        with open(submission_path, "rb") as sf:
            data = {"xml_submission_file": sf}
            request = self.factory.post(f"/{self.user.username}/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)

        self.assertContains(
            response,
            "Duplicate submission",
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
        self.assertEqual(
            response["Location"],
            f"http://testserver/{self.user.username}/submission",
        )
        self.assertEqual(Instance.objects.count(), 1)

    def test_duplicate_submission_extra_attachments(self):
        """Extra attachments from duplicate submission are saved."""
        # Existing submission
        survey = self.surveys[0]
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            survey + ".xml",
        )
        media_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            "1335783522563.jpg",
        )
        self._make_submission_w_attachment(submission_path, media_path)
        self.assertEqual(Instance.objects.count(), 1)
        self.assertEqual(Attachment.objects.count(), 1)

        # Make duplicate submission
        # Extra attachment
        media_path_2 = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            "1335783522564.JPG",
        )
        with open(submission_path, "rb") as sf, open(media_path, "rb") as mf, open(
            media_path_2, "rb"
        ) as mf2:
            data = {
                "xml_submission_file": sf,
                "media_file": mf,
                "media_file_2": mf2,
            }
            request = self.factory.post(f"/{self.user.username}/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)

        self.assertContains(
            response,
            "Duplicate submission",
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
        self.assertEqual(
            response["Location"],
            f"http://testserver/{self.user.username}/submission",
        )
        self.assertEqual(Instance.objects.count(), 1)
        self.assertEqual(Attachment.objects.count(), 2)
        self.assertTrue(Attachment.objects.filter(name="1335783522563.jpg").exists())
        self.assertTrue(Attachment.objects.filter(name="1335783522564.JPG").exists())

        # Simulate duplicate submission with multiple attachments with the same name
        # which occurred in  versions < v5.2.0
        instance = Instance.objects.first()
        Attachment.objects.create(
            xform=self.xform,
            instance=instance,
            mimetype="image/jpeg",
            name="1335783522563.jpg",
            extension="jpg",
            user=self.user,
            media_file="1335783522563.jpg",
        )

        # Make duplicate submission
        with open(submission_path, "rb") as sf, open(media_path, "rb") as mf:
            data = {"xml_submission_file": sf, "media_file": mf}
            request = self.factory.post(f"/{self.user.username}/submission", data)
            response = self.view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = self.view(request, username=self.user.username)

        self.assertContains(
            response,
            "Duplicate submission",
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
        self.assertTrue(response.has_header("Date"))
        self.assertEqual(response["Content-Type"], "text/xml; charset=utf-8")
        self.assertEqual(
            response["Location"],
            f"http://testserver/{self.user.username}/submission",
        )
        self.assertEqual(Instance.objects.count(), 1)
        self.assertEqual(Attachment.objects.count(), 3)
        self.assertEqual(Attachment.objects.filter(name="1335783522563.jpg").count(), 2)


class EditSubmissionTestCase(TestAbstractViewSet, TransactionTestCase):
    """Tests for editing submissions via XFormSubmissionViewSet."""

    def setUp(self):
        super().setUp()
        self.view = XFormSubmissionViewSet.as_view({"post": "update"})
        self._publish_xls_form_to_project()

    def test_edit_unencrypted_submission(self):
        """Editing a submission for a non-managed form (no encryption)."""
        # Create initial submission
        survey = self.surveys[0]
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            survey + ".xml",
        )
        self._make_submission(submission_path)
        self.assertEqual(Instance.objects.count(), 1)
        instance = Instance.objects.first()
        original_uuid = instance.uuid

        # Edit the submission
        edit_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            f"{survey}_edited.xml",
        )

        with open(edit_submission_path, "rb") as sf:
            data = {"xml_submission_file": sf}
            request = self.factory.post(
                f"/enketo/{self.xform.pk}/submission/{instance.pk}", data
            )
            request.user = AnonymousUser()
            response = self.view(request, xform_pk=self.xform.pk, pk=instance.pk)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIn("Successful submission", response.data.get("message", ""))

        # Verify the submission was edited
        # The instance count stays the same but the uuid changes
        self.assertEqual(Instance.objects.count(), 1)
        edited_instance = Instance.objects.first()
        new_uuid = "6b2cc313-fc09-437e-8139-fcd32f695d41"
        self.assertEqual(edited_instance.uuid, new_uuid)
        self.assertNotEqual(edited_instance.uuid, original_uuid)

    @patch("onadata.libs.serializers.data_serializer.safe_create_instance")
    @patch("onadata.libs.serializers.data_serializer.decrypt_submission")
    @patch("onadata.libs.serializers.data_serializer.get_kms_client")
    def test_edit_encrypted_submission(
        self, mock_get_kms_client, mock_decrypt, mock_safe_create
    ):
        """Editing an encrypted submission for a managed form."""
        from io import BytesIO

        # Publish encrypted form
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True
        self.xform.save()

        # Create KMSKey and XFormKey
        content_type = ContentType.objects.get_for_model(self.xform)
        kms_key = KMSKey.objects.create(
            key_id="test-key-id",
            public_key="test-pub-key",
            content_type=content_type,
            object_id=self.xform.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        submission_version = "2025051326"
        self.xform.kms_keys.create(version=submission_version, kms_key=kms_key)

        # Create a mock instance for safe_create_instance to return
        mock_instance = Instance(xform=self.xform, uuid="new-edited-uuid-1234")
        mock_instance.date_created = timezone.now()
        mock_instance.date_modified = timezone.now()
        mock_safe_create.return_value = (None, mock_instance)

        # Mock the decryption function to return decrypted content
        decrypted_xml = b"""<?xml version='1.0' ?>
        <data id="transportation_encrypted" version="2025051326">
            <transport>
                <loop_over_transport_types_frequency>
                    <ambulance>daily</ambulance>
                </loop_over_transport_types_frequency>
            </transport>
            <meta>
                <instanceID>uuid:new-edited-uuid-1234</instanceID>
                <deprecatedID>uuid:original-uuid</deprecatedID>
            </meta>
        </data>"""
        mock_decrypt.return_value = [
            ("submission.xml", BytesIO(decrypted_xml)),
        ]
        mock_get_kms_client.return_value = None

        # Edit the submission with encrypted content
        submission_xml_enc_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml.enc",
        )
        edit_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(edit_submission_path, "rb") as sf, open(
            submission_xml_enc_path, "rb"
        ) as mf:
            data = {"xml_submission_file": sf, "submission.xml.enc": mf}
            request = self.factory.post(f"/enketo/{self.xform.pk}/1/submission", data)
            request.user = AnonymousUser()
            response = self.view(request, xform_pk=self.xform.pk, pk=1)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify decryption was called
        mock_decrypt.assert_called_once()
        # Verify safe_create_instance was called with decrypted content
        mock_safe_create.assert_called_once()

    def test_edit_encryption_key_not_found(self):
        """Editing fails when encryption key is not found."""
        # Publish encrypted form
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True
        self.xform.save()

        # No encryption keys are set up, so edit should fail
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(submission_path, "rb") as sf:
            data = {"xml_submission_file": sf}
            request = self.factory.post(f"/enketo/{self.xform.pk}/1/submission", data)
            request.user = AnonymousUser()
            response = self.view(request, xform_pk=self.xform.pk, pk=1)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            response.render()
            self.assertIn("Encryption key not found", str(response.content))

    def test_edit_encryption_key_disabled(self):
        """Editing fails when encryption key is disabled."""
        # Publish encrypted form
        xlsform_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "transportation_encrypted.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.is_managed = True
        self.xform.save()

        # Create disabled KMSKey
        content_type = ContentType.objects.get_for_model(self.xform)
        kms_key = KMSKey.objects.create(
            key_id="test-key-id",
            public_key="test-pub-key",
            content_type=content_type,
            object_id=self.xform.pk,
            provider=KMSKey.KMSProvider.AWS,
            disabled_at=timezone.now(),  # Key is disabled
        )
        submission_version = "2025051326"
        self.xform.kms_keys.create(version=submission_version, kms_key=kms_key)

        # Attempt to edit - should fail because encryption key is disabled
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances_encrypted",
            "submission.xml",
        )

        with open(submission_path, "rb") as sf:
            data = {"xml_submission_file": sf}
            request = self.factory.post(f"/enketo/{self.xform.pk}/1/submission", data)
            request.user = AnonymousUser()
            response = self.view(request, xform_pk=self.xform.pk, pk=1)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            response.render()
            self.assertIn("Encryption key has been disabled", str(response.content))

    def test_edit_deletes_old_attachments(self):
        """Old attachments are soft-deleted when removed from an edited submission."""
        # Create initial submission with attachment
        survey = self.surveys[0]
        media_file = "1335783522563.jpg"
        media_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            media_file,
        )
        submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            survey + ".xml",
        )
        self._make_submission_w_attachment(submission_path, media_path)
        self.assertEqual(Instance.objects.count(), 1)
        self.assertEqual(Attachment.objects.count(), 1)

        instance = Instance.objects.first()
        old_attachment = Attachment.objects.first()
        self.assertIsNone(old_attachment.deleted_at)

        # Edit the submission with XML that no longer references the media
        edit_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            f"{survey}_edited_no_media.xml",
        )

        with open(edit_submission_path, "rb") as sf:
            data = {"xml_submission_file": sf}
            request = self.factory.post(
                f"/enketo/{self.xform.pk}/{instance.pk}/submission", data
            )
            request.user = AnonymousUser()
            response = self.view(request, xform_pk=self.xform.pk, pk=instance.pk)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        old_attachment.refresh_from_db()
        self.assertIsNotNone(old_attachment.deleted_at)
