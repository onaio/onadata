# -*- coding: utf-8 -*-
"""
Test XFormSubmissionViewSet module.
"""

import os
from builtins import open  # pylint: disable=redefined-builtin
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import UnreadablePostError
from django.test import TransactionTestCase
from django.urls.exceptions import NoReverseMatch
from rest_framework.reverse import reverse

import simplejson as json
from django_digest.test import DigestAuth

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet,
    add_uuid_to_submission_xml,
)
from onadata.apps.api.viewsets.xform_submission_viewset import XFormSubmissionViewSet
from onadata.apps.logger.models import Attachment, Instance, XForm
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

    @patch("onadata.apps.api.viewsets.xform_submission_viewset.SubmissionSerializer")  # noqa
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
