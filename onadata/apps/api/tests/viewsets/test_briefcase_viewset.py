# -*- coding: utf-8 -*-
"""
Test BriefcaseViewset
"""
import codecs
import os
import shutil
from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import storages
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from django_digest.test import DigestAuth

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.briefcase_viewset import (
    BriefcaseViewset,
    _query_optimization_fence,
)
from onadata.apps.api.viewsets.xform_submission_viewset import XFormSubmissionViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Instance, XForm

NUM_INSTANCES = 4
storage = storages["default"]


def ordered_instances(xform):
    return Instance.objects.filter(xform=xform).order_by("id")


class TestBriefcaseViewSet(TestAbstractViewSet):
    """
    Test BriefcaseViewset
    """

    def setUp(self):
        super().setUp()

        self.form_def_path = os.path.join(
            self.main_directory, "fixtures", "transportation", "transportation.xml"
        )
        self._submission_list_url = reverse(
            "view-submission-list", kwargs={"username": self.user.username}
        )
        self._submission_url = reverse(
            "submissions", kwargs={"username": self.user.username}
        )
        self._download_submission_url = reverse(
            "view-download-submission", kwargs={"username": self.user.username}
        )
        self._form_upload_url = reverse(
            "form-upload", kwargs={"username": self.user.username}
        )

    def _publish_xml_form(self, auth=None):
        view = BriefcaseViewset.as_view({"post": "create"})
        count = XForm.objects.count()

        with codecs.open(self.form_def_path, encoding="utf-8") as f:
            params = {"form_def_file": f, "dataFile": ""}
            auth = auth or DigestAuth(self.login_username, self.login_password)
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)

            self.assertEqual(XForm.objects.count(), count + 1)
            self.assertContains(response, "successfully published.", status_code=201)
        self.xform = XForm.objects.order_by("pk").reverse()[0]

    def test_retrieve_encrypted_form_submissions(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "api",
            "tests",
            "fixtures",
            "encrypted-form.xlsx",
        )
        submission_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "api",
            "tests",
            "fixtures",
            "encrypted-submission.xml",
        )
        self._publish_xls_form_to_project(xlsform_path=path)
        form = XForm.objects.filter(id_string="hh_survey2").first()
        self._make_submission(submission_path)

        # Ensure media_all_received is false on the submission
        # since the encrypted data wasn't sent alongside the submission
        self.assertEqual(form.instances.count(), 1)
        instance = form.instances.first()
        self.assertEqual(instance.total_media, 2)
        self.assertEqual(
            set(instance.get_expected_media()),
            set(["submission.xml.enc", "6-seater-7-15_15_11-15_45_15.jpg.enc"]),
        )
        self.assertFalse(instance.media_all_received)

        # Ensure submission is not returned on the Briefcase viewset
        request = self.factory.get(
            self._submission_list_url, data={"formId": form.id_string}
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["instances"].count(), 0)

    def test_view_submission_list(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        request = self.factory.get(
            self._submission_list_url, data={"formId": self.xform.id_string}
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "submissionList.xml",
        )
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, "rb", encoding="utf-8") as f:
            expected_submission_list = f.read()
            expected_submission_list = expected_submission_list.replace(
                "{{resumptionCursor}}", "%s" % last_index
            )
            self.assertContains(response, expected_submission_list)

    def test_view_submission_list_token_auth(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        # use Token auth in self.extra
        request = self.factory.get(
            self._submission_list_url,
            data={"formId": self.xform.id_string},
            **self.extra,
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "submissionList.xml",
        )
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, "rb", encoding="utf-8") as f:
            expected_submission_list = f.read()
            expected_submission_list = expected_submission_list.replace(
                "{{resumptionCursor}}", "%s" % last_index
            )
            self.assertContains(response, expected_submission_list)

    def test_view_submission_list_w_xformid(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        self._submission_list_url = reverse(
            "view-submission-list", kwargs={"xform_pk": self.xform.pk}
        )
        request = self.factory.get(
            self._submission_list_url, data={"formId": self.xform.id_string}
        )
        response = view(request, xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "submissionList.xml",
        )
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, "rb", encoding="utf-8") as f:
            expected_submission_list = f.read()
            expected_submission_list = expected_submission_list.replace(
                "{{resumptionCursor}}", "%s" % last_index
            )
            self.assertContains(response, expected_submission_list)

    def test_view_submission_list_w_projectid(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        self._submission_list_url = reverse(
            "view-submission-list", kwargs={"project_pk": self.xform.project.pk}
        )
        request = self.factory.get(
            self._submission_list_url, data={"formId": self.xform.id_string}
        )
        response = view(request, project_pk=self.xform.project.pk)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, project_pk=self.xform.project.pk)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "submissionList.xml",
        )
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, "rb", encoding="utf-8") as f:
            expected_submission_list = f.read()
            expected_submission_list = expected_submission_list.replace(
                "{{resumptionCursor}}", "%s" % last_index
            )
            self.assertContains(response, expected_submission_list)

    def test_view_submission_list_w_soft_deleted_submission(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        uuid = "f3d8dc65-91a6-4d0f-9e97-802128083390"

        # soft delete submission
        instance = Instance.objects.filter(uuid=uuid).first()
        instance.set_deleted(deleted_at=timezone.now())
        instance.save()

        request = self.factory.get(
            self._submission_list_url, data={"formId": self.xform.id_string}
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)

        self.assertEqual(response.status_code, 200)
        # check that number of instances returned by response is equal to
        # number of instances that have not been soft deleted
        self.assertEqual(
            response.data.get("instances").count(),
            Instance.objects.filter(xform=self.xform, deleted_at__isnull=True).count(),
        )

    def test_view_submission_list_w_deleted_submission(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        uuid = "f3d8dc65-91a6-4d0f-9e97-802128083390"
        Instance.objects.filter(uuid=uuid).order_by("id").delete()
        request = self.factory.get(
            self._submission_list_url, data={"formId": self.xform.id_string}
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "submissionList-4.xml",
        )
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES - 1)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, "rb", encoding="utf-8") as f:
            expected_submission_list = f.read()
            expected_submission_list = expected_submission_list.replace(
                "{{resumptionCursor}}", "%s" % last_index
            )
            self.assertContains(response, expected_submission_list)

        view = BriefcaseViewset.as_view({"get": "retrieve"})
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": uuid}
        )
        params = {"formId": formId}
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertTrue(response.status_code, 404)

    def test_view_submission_list_OtherUser(self):
        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        # alice cannot view bob's submissionList
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._create_user_profile(alice_data)
        auth = DigestAuth("alice", "bobbob")
        request = self.factory.get(
            self._submission_list_url, data={"formId": self.xform.id_string}
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 404)

    def test_view_submission_list_num_entries(self):
        def get_last_index(xform, last_index=None):
            instances = ordered_instances(xform)
            if not last_index and instances.count():
                return instances[instances.count() - 1].pk
            elif last_index:
                instances = instances.filter(pk__gt=last_index)
                if instances.count():
                    return instances[instances.count() - 1].pk
                else:
                    return get_last_index(xform)
            return 0

        view = BriefcaseViewset.as_view({"get": "list"})
        self._publish_xml_form()
        self._make_submissions()
        params = {"formId": self.xform.id_string}
        params["numEntries"] = 2
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[:2][1].pk
        last_expected_submission_list = ""
        for index in range(1, 5):
            auth = DigestAuth(self.login_username, self.login_password)
            request = self.factory.get(self._submission_list_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 200)
            if index > 2:
                last_index = get_last_index(self.xform, last_index)
            filename = "submissionList-%s.xml" % index
            if index == 4:
                self.assertContains(response, last_expected_submission_list)
                continue
            # set cursor for second request
            params["cursor"] = last_index
            submission_list_path = os.path.join(
                self.main_directory, "fixtures", "transportation", "view", filename
            )
            with codecs.open(submission_list_path, encoding="utf-8") as f:
                expected_submission_list = f.read()
                last_expected_submission_list = expected_submission_list = (
                    expected_submission_list.replace(
                        "{{resumptionCursor}}", "%s" % last_index
                    )
                )
                self.assertContains(response, expected_submission_list)
            last_index += 2

    def test_view_downloadSubmission(self):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        instance = Instance.objects.get(uuid=instanceId)
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        auth = DigestAuth(self.login_username, self.login_password)
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "downloadSubmission.xml",
        )
        with codecs.open(download_submission_path, encoding="utf-8") as f:
            text = f.read()
            for var in (
                ("{{submissionDate}}", instance.date_created.isoformat()),
                ("{{form_id}}", str(self.xform.id)),
                ("{{media_id}}", str(self.attachment.id)),
            ):
                text = text.replace(*var)
            self.assertContains(response, instanceId, status_code=200)
            self.assertMultiLineEqual(response.content.decode("utf-8"), text)

    def test_view_downloadSubmission_w_token_auth(self):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        instance = Instance.objects.get(uuid=instanceId)
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        # use Token auth in self.extra
        request = self.factory.get(
            self._download_submission_url, data=params, **self.extra
        )
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "downloadSubmission.xml",
        )
        with codecs.open(download_submission_path, encoding="utf-8") as f:
            text = f.read()
            for var in (
                ("{{submissionDate}}", instance.date_created.isoformat()),
                ("{{form_id}}", str(self.xform.id)),
                ("{{media_id}}", str(self.attachment.id)),
            ):
                text = text.replace(*var)
            self.assertContains(response, instanceId, status_code=200)
            self.assertMultiLineEqual(response.content.decode("utf-8"), text)

    def test_view_downloadSubmission_w_xformid(self):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        instance = Instance.objects.get(uuid=instanceId)
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        auth = DigestAuth(self.login_username, self.login_password)
        self._download_submission_url = reverse(
            "view-download-submission", kwargs={"xform_pk": self.xform.pk}
        )
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, xform_pk=self.xform.pk)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "downloadSubmission.xml",
        )
        with codecs.open(download_submission_path, encoding="utf-8") as f:
            text = f.read()
            for var in (
                ("{{submissionDate}}", instance.date_created.isoformat()),
                ("{{form_id}}", str(self.xform.id)),
                ("{{media_id}}", str(self.attachment.id)),
            ):
                text = text.replace(*var)
            self.assertContains(response, instanceId, status_code=200)
            self.assertMultiLineEqual(response.content.decode("utf-8"), text)

    def test_view_downloadSubmission_w_projectid(self):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        instance = Instance.objects.get(uuid=instanceId)
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        auth = DigestAuth(self.login_username, self.login_password)
        self._download_submission_url = reverse(
            "view-download-submission", kwargs={"project_pk": self.xform.project.pk}
        )
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, project_pk=self.xform.project.pk)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, project_pk=self.xform.project.pk)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "downloadSubmission.xml",
        )
        with codecs.open(download_submission_path, encoding="utf-8") as f:
            text = f.read()
            for var in (
                ("{{submissionDate}}", instance.date_created.isoformat()),
                ("{{form_id}}", str(self.xform.id)),
                ("{{media_id}}", str(self.attachment.id)),
            ):
                text = text.replace(*var)
            self.assertContains(response, instanceId, status_code=200)
            self.assertMultiLineEqual(response.content.decode("utf-8"), text)

    def test_view_downloadSubmission_OtherUser(self):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        # alice cannot view bob's downloadSubmission
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._create_user_profile(alice_data)
        auth = DigestAuth("alice", "bobbob")
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 404)

    def test_publish_xml_form_OtherUser(self):
        view = BriefcaseViewset.as_view({"post": "create"})
        # deno cannot publish form to bob's account
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._create_user_profile(alice_data)
        count = XForm.objects.count()

        with codecs.open(self.form_def_path, encoding="utf-8") as f:
            params = {"form_def_file": f, "dataFile": ""}
            auth = DigestAuth("alice", "bobbob")
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertNotEqual(XForm.objects.count(), count + 1)
            self.assertEqual(response.status_code, 403)

    def test_publish_xml_form_where_filename_is_not_id_string(self):
        view = BriefcaseViewset.as_view({"post": "create"})
        form_def_path = os.path.join(
            self.main_directory, "fixtures", "transportation", "Transportation Form.xml"
        )
        count = XForm.objects.count()
        with codecs.open(form_def_path, encoding="utf-8") as f:
            params = {"form_def_file": f, "dataFile": ""}
            auth = DigestAuth(self.login_username, self.login_password)
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertEqual(XForm.objects.count(), count + 1)
            self.assertContains(response, "successfully published.", status_code=201)

    def test_form_upload(self):
        view = BriefcaseViewset.as_view({"post": "create"})
        self._publish_xml_form()

        with codecs.open(self.form_def_path, encoding="utf-8") as f:
            params = {"form_def_file": f, "dataFile": ""}
            auth = DigestAuth(self.login_username, self.login_password)
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {"message": "Form with this id or SMS-keyword already exists."},
            )

    def test_upload_head_request(self):
        view = BriefcaseViewset.as_view({"head": "create"})

        auth = DigestAuth(self.login_username, self.login_password)
        request = self.factory.head(self._form_upload_url)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response.has_header("X-OpenRosa-Version"))
        self.assertTrue(response.has_header("X-OpenRosa-Accept-Content-Length"))
        self.assertTrue(response.has_header("Date"))

    def test_submission_with_instance_id_on_root_node(self):
        view = XFormSubmissionViewSet.as_view({"post": "create"})
        self._publish_xml_form()
        message = "Successful submission."
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        self.assertRaises(Instance.DoesNotExist, Instance.objects.get, uuid=instanceId)
        submission_path = os.path.join(
            self.main_directory, "fixtures", "transportation", "view", "submission.xml"
        )
        count = Instance.objects.count()
        with codecs.open(submission_path, encoding="utf-8") as f:
            post_data = {"xml_submission_file": f}
            request = self.factory.post(self._submission_list_url, post_data)
            response = view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth("bob", "bobbob")
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertContains(response, message, status_code=201)
            self.assertContains(response, instanceId, status_code=201)
            self.assertEqual(Instance.objects.count(), count + 1)

    def test_form_export_with_no_xlsform_returns_200(self):
        self._publish_xml_form()
        self.view = XFormViewSet.as_view({"get": "retrieve"})

        xform = XForm.objects.get(id_string="transportation_2011_07_25")
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=xform.pk, format="csv")

        self.assertEqual(response.status_code, 200)

        self.view = XFormViewSet.as_view({"get": "form"})
        response = self.view(request, pk=xform.pk, format="xls")
        self.assertEqual(response.status_code, 404)

    @patch.object(BriefcaseViewset, "get_object")
    def test_view_downloadSubmission_no_xmlns(self, mock_get_object):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        instance = Instance.objects.get(uuid=instanceId)
        instance.xml = '<?xml version=\'1.0\' ?><transportation xlmns="http://opendatakit.org/submission" id="transportation_2011_07_25"><transport><available_transportation_types_to_referral_facility>none</available_transportation_types_to_referral_facility><available_transportation_types_to_referral_facility>none</available_transportation_types_to_referral_facility><loop_over_transport_types_frequency><ambulance /><bicycle /><boat_canoe /><bus /><donkey_mule_cart /><keke_pepe /><lorry /><motorbike /><taxi /><other /></loop_over_transport_types_frequency></transport><meta><instanceID>uuid:5b2cc313-fc09-437e-8149-fcd32f695d41</instanceID></meta></transportation>\n'  # noqa
        mock_get_object.return_value = instance
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        auth = DigestAuth(self.login_username, self.login_password)
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "downloadSubmission.xml",
        )
        with codecs.open(download_submission_path, encoding="utf-8") as f:
            text = f.read()
            for var in (
                ("{{submissionDate}}", instance.date_created.isoformat()),
                ("{{form_id}}", str(self.xform.id)),
                ("{{media_id}}", str(self.attachment.id)),
            ):
                text = text.replace(*var)
            self.assertNotIn(
                'transportation id="transportation_2011_07_25"'
                ' instanceID="uuid:5b2cc313-fc09-437e-8149-fcd32f695d41"'
                f' submissionDate="{ instance.date_created.isoformat() }" '
                'xlmns="http://opendatakit.org/submission"',
                text,
            )
            self.assertContains(response, instanceId, status_code=200)

        with override_settings(SUPPORT_BRIEFCASE_SUBMISSION_DATE=False):
            request = self.factory.get(self._download_submission_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            response.render()
            self.assertIn(
                'transportation xlmns="http://opendatakit.org/submission"'
                ' id="transportation_2011_07_25"'
                ' instanceID="uuid:5b2cc313-fc09-437e-8149-fcd32f695d41"'
                f' submissionDate="{ instance.date_created.isoformat() }"',
                response.content.decode("utf-8"),
            )

    @patch.object(BriefcaseViewset, "get_object")
    def test_view_downloadSubmission_multiple_nodes(self, mock_get_object):
        view = BriefcaseViewset.as_view({"get": "retrieve"})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = "5b2cc313-fc09-437e-8149-fcd32f695d41"
        instance = Instance.objects.get(uuid=instanceId)
        instance.xml = "<?xml version='1.0' ?><transportation id=\"transportation_2011_07_25\"><transport><available_transportation_types_to_referral_facility>none</available_transportation_types_to_referral_facility><available_transportation_types_to_referral_facility>none</available_transportation_types_to_referral_facility><loop_over_transport_types_frequency><ambulance /><bicycle /><boat_canoe /><bus /><donkey_mule_cart /><keke_pepe /><lorry /><motorbike /><taxi /><other /></loop_over_transport_types_frequency></transport><meta><instanceID>uuid:5b2cc313-fc09-437e-8149-fcd32f695d41</instanceID></meta></transportation>\n"  # noqa
        mock_get_object.return_value = instance
        formId = (
            "%(formId)s[@version=null and @uiVersion=null]/"
            "%(formId)s[@key=uuid:%(instanceId)s]"
            % {"formId": self.xform.id_string, "instanceId": instanceId}
        )
        params = {"formId": formId}
        auth = DigestAuth(self.login_username, self.login_password)
        request = self.factory.get(self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "view",
            "downloadSubmission.xml",
        )
        with codecs.open(download_submission_path, encoding="utf-8") as f:
            text = f.read()
            for var in (
                ("{{submissionDate}}", instance.date_created.isoformat()),
                ("{{form_id}}", str(self.xform.id)),
                ("{{media_id}}", str(self.attachment.id)),
            ):
                text = text.replace(*var)
            self.assertContains(response, instanceId, status_code=200)

    def test_query_optimization_fence(self):
        self._publish_xml_form()
        self._make_submissions()
        instances = ordered_instances(self.xform)
        optimized_instances = _query_optimization_fence(instances, 4)
        self.assertEqual(instances.count(), optimized_instances.count())
        op_sql_query = (
            'SELECT "logger_instance"."id", "logger_instance"."uuid" FROM "logger_instance"'
            f' WHERE "logger_instance"."id" IN ({optimized_instances[0].get("pk")},'
            f' {optimized_instances[1].get("pk")}, {optimized_instances[2].get("pk")},'
            f' {optimized_instances[3].get("pk")})'
        )
        self.assertEqual(str(optimized_instances.query), op_sql_query)

    def tearDown(self):
        # remove media files
        if self.user:
            if storage.exists(self.user.username):
                shutil.rmtree(storage.path(self.user.username))
