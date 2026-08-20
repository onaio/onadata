import os
from urllib.parse import parse_qs

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import requests
from httmock import HTTMock, urlmatch

from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.views import edit_data
from onadata.apps.logger.xform_instance_parser import get_uuid_from_xml
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.logger_tools import inject_instanceid, save_attachments


@urlmatch(netloc=r"(.*\.)?enketo\.ona\.io$")
def enketo_edit_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"edit_url": "https://hmh2a.enketo.ona.io"}'
    return response


def enketo_edit_capture_mock(captured):
    """``enketo_edit_mock``, recording the request body into ``captured``."""

    @urlmatch(netloc=r"(.*\.)?enketo\.ona\.io$")
    def capture(url, request):
        captured["body"] = request.body

        return enketo_edit_mock(url, request)

    return capture


class TestWebforms(TestBase):
    def setUp(self):
        super(TestWebforms, self).setUp()
        self._publish_transportation_form_and_submit_instance()

    def __load_fixture(self, *path):
        with open(os.path.join(os.path.dirname(__file__), *path), "r") as f:
            return f.read()

    def __attach_media(self, instance, media_file):
        """Attach a fixture media file to an existing submission."""
        path = os.path.join(
            self.this_directory,
            "fixtures",
            "transportation",
            "instances",
            self.surveys[0],
            media_file,
        )
        with open(path, "rb") as f:
            upload = SimpleUploadedFile(media_file, f.read(), content_type="image/jpeg")
            save_attachments(self.xform, instance, [upload])

        return instance.attachments.get(name=media_file)

    def test_edit_url(self):
        instance = Instance.objects.order_by("id").reverse()[0]
        edit_url = reverse(
            edit_data,
            kwargs={
                "username": self.user.username,
                "id_string": self.xform.id_string,
                "data_id": instance.id,
            },
        )
        with HTTMock(enketo_edit_mock):
            response = self.client.get(edit_url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["location"], "https://hmh2a.enketo.ona.io")

    def test_edit_url_sends_instance_attachments(self):
        """The edit link request carries the submission's attachments.

        The instance XML records only their file names, so each is sent paired
        with an absolute download URL.
        """
        instance = Instance.objects.order_by("id").reverse()[0]
        attachment = self.__attach_media(instance, "1335783522563.jpg")
        edit_url = reverse(
            edit_data,
            kwargs={
                "username": self.user.username,
                "id_string": self.xform.id_string,
                "data_id": instance.id,
            },
        )

        captured = {}

        with HTTMock(enketo_edit_capture_mock(captured)):
            self.client.get(edit_url)

        posted = parse_qs(captured["body"])

        self.assertEqual(
            posted["instance_attachments[1335783522563.jpg]"],
            [
                "http://testserver/api/v1/files/"
                f"{attachment.pk}?filename={attachment.media_file.name}"
            ],
        )

    def test_inject_instanceid(self):
        """
        Test that 1 and only 1 instance id exists or is injected
        """
        instance = Instance.objects.all().reverse()[0]
        xml_str = self.__load_fixture(
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53.xml",
        )
        # test that we dont have an instance id
        uuid = get_uuid_from_xml(xml_str)
        self.assertIsNone(uuid)
        injected_xml_str = inject_instanceid(xml_str, instance.uuid)
        # check that xml has the instanceid tag
        uuid = get_uuid_from_xml(injected_xml_str)
        self.assertEqual(uuid, instance.uuid)

    def test_dont_inject_instanceid_if_exists(self):
        xls_file_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "tutorial", "tutorial.xlsx"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)
        xml_file_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "fixtures",
            "tutorial",
            "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
        )
        self._make_submission(xml_file_path)
        instance = Instance.objects.order_by("id").reverse()[0]
        injected_xml_str = inject_instanceid(instance.xml, instance.uuid)
        # check that the xml is unmodified
        self.assertEqual(instance.xml, injected_xml_str)
