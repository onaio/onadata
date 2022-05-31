# -*- coding: utf-8 -*-
"""
Test Briefcase client
"""
import os.path
import shutil
from io import BytesIO

from django.contrib.auth import authenticate
from django.core.files.storage import get_storage_class
from django.core.files.uploadedfile import UploadedFile
from django.test import RequestFactory
from django.urls import reverse

import requests
import requests_mock
from django_digest.test import Client as DigestClient
from flaky import flaky
from six.moves.urllib.parse import urljoin

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.views import download_xform, formList, xformsManifest
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import download_media_data, profile
from onadata.libs.utils.briefcase_client import BriefcaseClient

storage = get_storage_class()()


def form_list(request, context):
    """Return the /formList content"""
    context.status_code = 200
    req = RequestFactory().get("/bob/formList")
    req.user = authenticate(username="bob", password="bob")
    return formList(req, username="bob").content


def form_xml(request, context):
    """Return the /form.xml content"""
    context.status_code = 200
    req = RequestFactory().get("/bob/transportation_2011_07_25/form.xml")
    req.user = authenticate(username="bob", password="bob")
    return download_xform(
        req, username="bob", id_string="transportation_2011_07_25"
    ).content


def form_manifest(request, context):
    """Return the /xformsManifest/{pk} content"""
    context.status_code = 200
    req = RequestFactory().get(request.url)
    req.user = authenticate(username="bob", password="bob")
    return xformsManifest(
        req, username="bob", id_string="transportation_2011_07_25"
    ).content


def form_media(request, context):
    """Return the /form-media/{pk} content"""
    context.status_code = 200
    path = request.path
    req = RequestFactory().head(request.url)
    req.user = authenticate(username="bob", password="bob")
    data_id = path[path.rfind("/") + 1 :]
    response = download_media_data(
        req, username="bob", id_string="transportation_2011_07_25", data_id=data_id
    )
    ids = list(Instance.objects.values_list("id", flat=True))
    xids = list(XForm.objects.values_list("id", flat=True))
    assert (
        response.status_code == 200
    ), f"{data_id} - {response.content} {response.status_code} -{ids} {xids} {path}"
    return get_streaming_content(response)


def submission_list(request, context):
    """Return the /submissionList content"""
    response = requests.Response()
    client = DigestClient()
    client.set_authorization("bob", "bob", "Digest")
    res = client.get(f"{request.url}")
    if res.status_code == 302:
        res = client.get(res["Location"])
        assert res.status_code == 200, res.content
        response.encoding = res.get("content-type")
        return get_streaming_content(res)
    context.status_code = 200
    return res.content


def get_streaming_content(res):
    """Return the contents of ``res.streaming_content``."""
    tmp = BytesIO()
    for chunk in res.streaming_content:
        tmp.write(chunk)
    content = tmp.getvalue()
    tmp.close()
    return content


@flaky(max_runs=3)
class TestBriefcaseClient(TestBase):
    """Test briefcase_client module."""

    def setUp(self):
        TestBase.setUp(self)
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        src = os.path.join(
            self.this_directory, "fixtures", "transportation", "screenshot.png"
        )
        with open(src, "rb") as f:
            media_file = UploadedFile(file=f, content_type="image/png")
            count = MetaData.objects.count()
            media = MetaData.media_upload(self.xform, media_file)
            self.assertEqual(MetaData.objects.count(), count + 1)
            self.media = media[0]
            url = urljoin(
                self.base_url, reverse(profile, kwargs={"username": self.user.username})
            )
            self._logout()
            self._create_user_and_login("deno", "deno")
            self.briefcase_client = BriefcaseClient(
                username="bob", password="bob", url=url, user=self.user
            )

    def _download_xforms(self):
        with requests_mock.Mocker() as mocker:
            mocker.get("/bob/formList", content=form_list)
            mocker.get(
                "/bob/forms/transportation_2011_07_25/form.xml", content=form_xml
            )
            mocker.get(f"/bob/xformsManifest/{self.media.pk}", content=form_manifest)
            mocker.head(
                f"/bob/forms/transportation_2011_07_25/formid-media/{self.media.pk}",
                content=form_media,
            )
            mocker.get(
                f"/bob/forms/transportation_2011_07_25/formid-media/{self.media.pk}",
                content=form_media,
            )
            self.briefcase_client.download_xforms()

    def _download_submissions(self):
        id_string = "transportation_2011_07_25"
        with requests_mock.Mocker() as mocker:
            mocker.get(
                (
                    "/bob/view/submissionList"
                    f"?formId={id_string}&numEntries=100&cursor=0"
                ),
                content=submission_list,
            )
            mocker.get(
                (
                    "/bob/view/submissionList"
                    f"?formId={id_string}&numEntries=100&cursor=1"
                ),
                content=submission_list,
            )
            mocker.get(
                (
                    "/bob/view/downloadSubmission"
                    f"?formId={id_string}%5B%40version%3Dnull+and+%40uiVersion%3D"
                    f"null%5D%2F{id_string}"
                    f"%5B%40key%3Duuid%3A5b2cc313-fc09-437e-8149-fcd32f695d41%5D"
                ),
                content=submission_list,
            )
            mocker.head(
                (
                    "/attachment/original?media_file=bob/attachments/"
                    f"{self.media.pk}_{id_string}/1335783522563.jpg"
                ),
                content=submission_list,
            )
            mocker.get(
                (
                    "/attachment/original?media_file=bob/attachments/"
                    f"{self.media.pk}_{id_string}/1335783522563.jpg"
                ),
                content=submission_list,
            )
            self.briefcase_client.download_instances(self.xform.id_string)

    def test_download_xform_xml(self):
        """
        Download xform via briefcase api
        """
        self._download_xforms()
        forms_folder_path = os.path.join(
            "deno", "briefcase", "forms", self.xform.id_string
        )
        self.assertTrue(storage.exists(forms_folder_path))
        forms_path = os.path.join(forms_folder_path, f"{self.xform.id_string}.xml")
        self.assertTrue(storage.exists(forms_path))
        form_media_path = os.path.join(forms_folder_path, "form-media")
        self.assertTrue(storage.exists(form_media_path))
        media_path = os.path.join(form_media_path, "screenshot.png")
        self.assertTrue(storage.exists(media_path))

        self._download_submissions()
        instance_folder_path = os.path.join(
            "deno", "briefcase", "forms", self.xform.id_string, "instances"
        )
        self.assertTrue(storage.exists(instance_folder_path))
        instance = Instance.objects.all()[0]
        instance_path = os.path.join(
            instance_folder_path, f"uuid{instance.uuid}", "submission.xml"
        )
        self.assertTrue(storage.exists(instance_path))
        media_file = "1335783522563.jpg"
        media_path = os.path.join(
            instance_folder_path, f"uuid{instance.uuid}", media_file
        )
        self.assertTrue(storage.exists(media_path))

    def test_push(self):
        """Test ODK briefcase client push function."""
        self._download_xforms()
        self._download_submissions()
        XForm.objects.all().delete()
        xforms = XForm.objects.filter(user=self.user, id_string=self.xform.id_string)
        self.assertEqual(xforms.count(), 0)
        instances = Instance.objects.filter(
            xform__user=self.user, xform__id_string=self.xform.id_string
        )
        self.assertEqual(instances.count(), 0)
        self.briefcase_client.push()
        xforms = XForm.objects.filter(user=self.user, id_string=self.xform.id_string)
        self.assertEqual(xforms.count(), 1)
        instances = Instance.objects.filter(
            xform__user=self.user, xform__id_string=self.xform.id_string
        )
        self.assertEqual(instances.count(), 1)

    def tearDown(self):
        # remove media files
        for username in ["bob", "deno"]:
            if storage.exists(username):
                shutil.rmtree(storage.path(username))
