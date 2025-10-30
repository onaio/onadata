# -*- coding: utf-8 -*-
"""
Test logger_tools utility functions.
"""

import os
import re
from datetime import timedelta
from io import BytesIO
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http.request import HttpRequest
from django.test.utils import override_settings
from django.utils import timezone

from azure.storage.blob import AccountSasPermissions
from defusedxml.ElementTree import ParseError

from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.models import Instance
from onadata.apps.logger.xform_instance_parser import AttachmentNameError
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.test_utils.pyxform_test_case import PyxformTestCase
from onadata.libs.utils.common_tags import MEDIA_ALL_RECEIVED, MEDIA_COUNT, TOTAL_MEDIA
from onadata.libs.utils.logger_tools import (
    create_instance,
    delete_xform_submissions,
    generate_content_disposition_header,
    get_storages_media_download_url,
    response_with_mimetype_and_name,
    safe_create_instance,
)


class TestLoggerTools(PyxformTestCase, TestBase):
    """
    Test logger_tools utility functions.
    """

    # pylint: disable=invalid-name
    def test_generate_content_disposition_header(self):
        """Test generate_content_disposition_header() function."""
        file_name = "export"
        extension = "ext"

        date_pattern = "\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}"  # noqa
        file_name_pattern = f"{file_name}.{extension}"
        file_name_with_timestamp_pattern = f"{file_name}-{date_pattern}.{extension}"
        return_value_with_no_name = generate_content_disposition_header(None, extension)
        self.assertEqual(return_value_with_no_name, "attachment;")

        return_value_with_name_and_no_show_date = generate_content_disposition_header(
            file_name, extension
        )
        self.assertTrue(
            re.search(
                file_name_with_timestamp_pattern,
                return_value_with_name_and_no_show_date,
            )
        )

        return_value_with_name_and_false_show_date = (
            generate_content_disposition_header(file_name, extension, False)
        )
        self.assertTrue(
            re.search(file_name_pattern, return_value_with_name_and_false_show_date)
        )

    def test_generate_content_disposition_w_non_ascii_name(self):
        """Content disposition header is generated correctly for non-ASCII name."""
        file_name = "exporté"
        extension = "csv"
        return_value = generate_content_disposition_header(
            file_name, extension, show_date=False
        )
        self.assertEqual(
            return_value,
            "attachment; filename=\"download.csv\"; filename*=UTF-8''export%C3%A9.csv",
        )

    def test_attachment_tracking(self):
        """
        Test that when a submission with many attachments is made,
        we keep track of the total number of attachments expected
        and if we have received all of them
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | image | image1 | Photo |
        |        | image | image2 | Photo |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """
        file_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health_2011_03_13."
            "xml_2011-03-15_20-30-28/1300221157303.jpg"
        )
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg"
        )
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media_file],
        )
        instance.refresh_from_db()
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance.json[MEDIA_COUNT], 1)
        self.assertEqual(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEqual(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEqual(instance.json[MEDIA_ALL_RECEIVED], instance.media_all_received)
        file2_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/"
            "Water_2011_03_17_2011-03-17_16-29-59/1300375832136.jpg"
        )
        media2_file = django_file(
            path=file2_path, field_name="image2", content_type="image/jpeg"
        )
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media2_file],
        )
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance2.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance2.json[MEDIA_COUNT], 2)
        self.assertEqual(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEqual(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEqual(
            instance2.json[MEDIA_ALL_RECEIVED], instance2.media_all_received
        )
        media2_file = django_file(
            path=file2_path, field_name="image2", content_type="image/jpeg"
        )
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media2_file],
        )
        instance3 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance3.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance3.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance3.json[MEDIA_COUNT], 2)
        self.assertEqual(instance3.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEqual(instance3.json[MEDIA_COUNT], instance2.media_count)
        self.assertEqual(
            instance3.json[MEDIA_ALL_RECEIVED], instance3.media_all_received
        )

    def test_attachment_tracking_for_repeats(self):
        """
        Test that when a submission with many attachments is made,
        we keep track of the total number of attachments expected
        and if we have received all of them
        """
        md = """
        | survey |              |        |        |
        |        | type         | name   | label  |
        |        | begin repeat | images | Photos |
        |        | image        | image1 | Photo  |
        |        | end repeat   |        |        |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
            </meta>
            <images>
                <image1>1300221157303.jpg</image1>
            </images>
            <images>
                <image1>1300375832136.jpg</image1>
            </images>
        </data>
        """
        file_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health_2011_03_13."
            "xml_2011-03-15_20-30-28/1300221157303.jpg"
        )
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg"
        )
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media_file],
        )
        instance.refresh_from_db()
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance.json[MEDIA_COUNT], 1)
        self.assertEqual(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEqual(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEqual(instance.json[MEDIA_ALL_RECEIVED], instance.media_all_received)
        file2_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/"
            "Water_2011_03_17_2011-03-17_16-29-59/1300375832136.jpg"
        )
        media2_file = django_file(
            path=file2_path, field_name="image1", content_type="image/jpeg"
        )
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media2_file],
        )
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance2.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance2.json[MEDIA_COUNT], 2)
        self.assertEqual(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEqual(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEqual(
            instance2.json[MEDIA_ALL_RECEIVED], instance2.media_all_received
        )

    def test_attachment_tracking_for_nested_repeats(self):
        """
        Test that when a submission with many attachments is made,
        we keep track of the total number of attachments expected
        and if we have received all of them
        """
        md = """
        | survey |              |        |        |
        |        | type         | name   | label  |
        |        | begin repeat | images | Photos |
        |        | begin repeat | g      | G      |
        |        | image        | image1 | Photo  |
        |        | end repeat   |        |        |
        |        | end repeat   |        |        |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8n851AsKaqBPO5VN7</instanceID>
            </meta>
            <images>
                <g><image1>1300221157303.jpg</image1></g>
            </images>
            <images>
                <g><image1>1300375832136.jpg</image1></g>
            </images>
        </data>
        """
        file_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health_2011_03_13."
            "xml_2011-03-15_20-30-28/1300221157303.jpg"
        )
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg"
        )
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media_file],
        )
        instance.refresh_from_db()
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance.json[MEDIA_COUNT], 1)
        self.assertEqual(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEqual(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEqual(instance.json[MEDIA_ALL_RECEIVED], instance.media_all_received)
        file2_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/"
            "Water_2011_03_17_2011-03-17_16-29-59/1300375832136.jpg"
        )
        media2_file = django_file(
            path=file2_path, field_name="image1", content_type="image/jpeg"
        )
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media2_file],
        )
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance2.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance2.json[MEDIA_COUNT], 2)
        self.assertEqual(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEqual(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEqual(
            instance2.json[MEDIA_ALL_RECEIVED], instance2.media_all_received
        )

    def test_replaced_attachments_not_tracked(self):
        """
        Test that when a submission with an attachments is made,
        and later edited, whereby the attachment is replaced,
        the replaced attachment is no longer tracked for that
        submission
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | file  | file   | File  |
        |        | image | image  | Image |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
            </meta>
            <file>Health_2011_03_13.xml_2011-03-15_20-30-28.xml</file>
            <image>1300221157303.jpg</image>
        </data>
        """
        media_root = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health"
            "_2011_03_13.xml_2011-03-15_20-30-28/"
        )
        image_media = django_file(
            path=f"{media_root}1300221157303.jpg",
            field_name="image",
            content_type="image/jpeg",
        )
        file_media = django_file(
            path=f"{media_root}Health_2011_03_13.xml_2011-03-15_20-30-28.xml",
            field_name="file",
            content_type="text/xml",
        )
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[file_media, image_media],
        )
        instance.refresh_from_db()
        self.assertTrue(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(
            instance.attachments.filter(deleted_at__isnull=True).count(), 2
        )
        self.assertEqual(instance.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance.json[MEDIA_COUNT], 2)
        self.assertEqual(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEqual(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEqual(instance.json[MEDIA_ALL_RECEIVED], instance.media_all_received)
        patch_value = "onadata.apps.logger.models.Instance.get_expected_media"
        with patch(patch_value) as get_expected_media:
            get_expected_media.return_value = ["1300375832136.jpg"]
            updated_xml_string = f"""
            <data id="{xform.id_string}">
                <meta>
                    <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
                </meta>
                <images>
                    <image1>1300375832136.jpg</image1>
                </images>
            </data>
            """
            file2_path = (
                f"{settings.PROJECT_ROOT}/apps/logger/tests/Water_2011_03_17_2011"
                "-03-17_16-29-59/1300375832136.jpg"
            )
            media2_file = django_file(
                path=file2_path, field_name="image1", content_type="image/jpeg"
            )
            create_instance(
                self.user.username,
                BytesIO(updated_xml_string.strip().encode("utf-8")),
                media_files=[media2_file],
            )

            instance2 = Instance.objects.get(pk=instance.pk)
            self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
            # Test that only one attachment is recognised for this submission
            # Since the file is no longer present in the submission
            self.assertEqual(instance2.json[TOTAL_MEDIA], 1)
            self.assertEqual(instance2.json[MEDIA_COUNT], 1)
            self.assertEqual(instance2.json[TOTAL_MEDIA], instance2.total_media)
            self.assertEqual(instance2.json[MEDIA_COUNT], instance2.media_count)
            self.assertEqual(
                instance2.json[MEDIA_ALL_RECEIVED], instance2.media_all_received
            )

    def test_attachment_tracking_duplicate(self):
        """
        Test that duplicate attachments does not affect if all attachments were
        received.
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | image | image1 | Photo |
        |        | image | image2 | Photo |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """
        file_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health_2011_03_13."
            "xml_2011-03-15_20-30-28/1300221157303.jpg"
        )
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg"
        )
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media_file],
        )
        instance.refresh_from_db()
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance.json[MEDIA_COUNT], 1)
        self.assertEqual(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEqual(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEqual(instance.json[MEDIA_ALL_RECEIVED], instance.media_all_received)
        media2_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg"
        )
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media2_file],
        )
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertFalse(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance2.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance2.json[MEDIA_COUNT], 1)
        self.assertEqual(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEqual(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEqual(
            instance2.json[MEDIA_ALL_RECEIVED], instance2.media_all_received
        )

    def test_attachment_tracking_not_in_submission(self):
        """
        Test attachment not in submission is not saved.
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | image | image1 | Photo |
        |        | image | image2 | Photo |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """
        file_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health_2011_03_13."
            "xml_2011-03-15_20-30-28/1300221157303.jpg"
        )
        file2_path = (
            f"{settings.PROJECT_ROOT}/libs/tests/utils/fixtures/"
            "tutorial/instances/uuid1/1442323232322.jpg"
        )
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg"
        )
        media2_file = django_file(
            path=file2_path, field_name="image1", content_type="image/jpeg"
        )
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[media_file, media2_file],
        )
        instance.refresh_from_db()
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEqual(instance.json[TOTAL_MEDIA], 2)
        self.assertEqual(instance.json[MEDIA_COUNT], 1)
        self.assertEqual(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEqual(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEqual(instance.json[MEDIA_ALL_RECEIVED], instance.media_all_received)

    def test_check_encryption_status(self):
        """
        Test that the encryption status of a submission is checked and
        unencrypted submissions are rejected when made to encrypted forms.
        """
        form_path = (
            f"{settings.PROJECT_ROOT}/libs/tests/"
            "fixtures/tutorial/tutorial_encrypted.xlsx"
        )
        self._publish_xls_file_and_set_xform(form_path)
        instance_xml = f"""
        <data xmlns:jr="http://openrosa.org/javarosa"
            xmlns:orx="http://openrosa.org/xforms" id="{self.xform.id_string}" version="{self.xform.version}">
            <name>Bob</name>
            <age>20</age>
            <picture/>
            <has_children>0</has_children>
            <gps/>
            <web_browsers>firefox chrome safari</web_browsers>
            <meta>
                <instanceID>uuid:332f956b-b923-4f88-899d-849485ae66d0</instanceID>
            </meta>
        </data>
        """  # noqa
        req = HttpRequest()
        req.user = self.user
        ret = safe_create_instance(
            self.user.username,
            BytesIO(instance_xml.strip().encode("utf-8")),
            [],
            None,
            req,
        )
        response = ret[0]
        expected_error = "Unencrypted submissions are not allowed for encrypted forms."
        self.assertIsNone(ret[1])
        self.assertEqual(response.status_code, 400)
        self.assertIn(expected_error, str(response.content))

        # Test incorrectly formatted encrypted submission is rejected
        instance_xml = f"""
        <data id="{self.xform.id_string}" version="{self.xform.version}" encrypted="yes"
            xmlns="http://www.opendatakit.org/xforms/encrypted">
            <orx:meta xmlns:orx="http://openrosa.org/xforms">
                <orx:instanceID>uuid:6850c987-fcd6-4469-a843-7ce200af00e2</orx:instanceID>
            </orx:meta>\n<encryptedXmlFile>submission.xml.enc</encryptedXmlFile>
            <base64EncryptedElementSignature>PfYw8EIFutyhT03rdOf6rT/1FuETsOHbcnIOJdB9qBre7BWGu0k4fRUpv3QdyTil9wCez64MyOXbsHzFyTcazAkBmBPKuqiK7k3dws57rRuJEpmLjOtniQoAuTaXnAlTwp2x6KEvLt9Kqfa8kD8cFvwsRBs8rvkolAl33UAuNjzO7j9h0N94R9syqc6jNR5gGGaG74KlhYvAZnekoPXGb3MjZMDqjCSnYdiPz8iVOUsPBvuitzYIqGdfe1sW8EkQBOp0ACsD31EQ03iWyb8Mg5JSTCdz7T+qdtd0R65EjQ4ZTpDv72/owocteXVV6dCKi564YFXbiwpdkzf80B+QoQ==</base64EncryptedElementSignature>
        </data>
        """  # noqa
        ret = safe_create_instance(
            self.user.username,
            BytesIO(instance_xml.strip().encode("utf-8")),
            [],
            None,
            req,
        )
        response = ret[0]
        expected_error = "Encrypted submission incorrectly formatted."
        self.assertIsNone(ret[1])
        self.assertEqual(response.status_code, 400)
        self.assertIn(expected_error, str(response.content))

    def test_attachment_file_name_validation(self):
        """
        Test that a clear exception is raised when an attachement
        is received whose file name exceeds 100 chars
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | image | image1 | Photo |
        |        | image | image2 | Photo |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """
        file_path = (
            f"{settings.PROJECT_ROOT}/apps/logger/tests/Health_2011_03_13."
            "xml_2011-03-15_20-30-28/1300221157303.jpg"
        )
        with open(file_path, "rb") as f:
            media_file = InMemoryUploadedFile(
                file=f,
                field_name="image1",
                name=(
                    f"{f.name}test_file_name_test_file_name_test_file_name_"
                    "test_file_name_test_file_name_test_file_name"
                ),
                content_type="image/jpeg",
                size=os.path.getsize(file_path),
                charset=None,
            )
            with self.assertRaises(AttachmentNameError):
                create_instance(
                    self.user.username,
                    BytesIO(xml_string.strip().encode("utf-8")),
                    media_files=[media_file],
                )

    def test_handle_parse_error(self):
        """
        Test that an invalid XML results is handled
        """
        self._create_user_and_login()

        xml_string = """
        <data id="id_string">
            <meta>
                <instanceID>uuid:368f423e-6350-43b2-b061-7baae01aacdb
        """

        req = HttpRequest()
        req.user = self.user
        with patch(
            "onadata.libs.utils.logger_tools.create_instance"
        ) as create_instance_mock:
            create_instance_mock.side_effect = [ParseError]
            ret = safe_create_instance(
                self.user.username,
                BytesIO(xml_string.strip().encode("utf-8")),
                [],
                None,
                req,
            )
            self.assertContains(ret[0].content.decode(), "Improperly formatted XML.")


class DeleteXFormSubmissionsTestCase(TestBase):
    """Tests for method `delete_xform_submissions`"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self._make_submissions()
        self.instances = self.xform.instances.all()

    def test_soft_delete_all(self):
        """All submissions are soft deleted"""
        delete_xform_submissions(self.xform, self.user)

        self.assertEqual(Instance.objects.filter(deleted_at__isnull=False).count(), 4)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_submissions, 0)

    @override_settings(ENABLE_SUBMISSION_PERMANENT_DELETE=True)
    def test_hard_delete_all(self):
        """All submissions are hard deleted"""
        delete_xform_submissions(self.xform, self.user, soft_delete=False)

        self.assertEqual(Instance.objects.count(), 0)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_submissions, 0)

    def test_soft_delete_subset(self):
        """Subset of submissions are soft deleted"""
        delete_xform_submissions(
            self.xform, self.user, instance_ids=[self.instances[0].pk]
        )

        self.assertEqual(Instance.objects.filter(deleted_at__isnull=False).count(), 1)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_submissions, 3)

    @override_settings(ENABLE_SUBMISSION_PERMANENT_DELETE=True)
    def test_hard_delete_subset(self):
        """Subset of submissions are hard deleted"""
        delete_xform_submissions(
            self.xform,
            self.user,
            instance_ids=[self.instances[0].pk],
            soft_delete=False,
        )

        self.assertEqual(Instance.objects.count(), 3)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_submissions, 3)

    def test_sets_deleted_at(self):
        """deleted_at is set to the current time"""
        mocked_now = timezone.now()

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            delete_xform_submissions(self.xform, self.user)

        self.assertTrue(
            all(instance.deleted_at == mocked_now for instance in self.instances)
        )

    def test_sets_date_modified(self):
        """date_modified is set to the current time"""
        mocked_now = timezone.now()

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            delete_xform_submissions(self.xform, self.user)

        self.assertTrue(
            all(instance.date_modified == mocked_now for instance in self.instances)
        )

    def test_sets_deleted_by(self):
        """Deleted_by is set to the user who initiated the deletion"""
        delete_xform_submissions(self.xform, self.user)

        self.assertTrue(
            all(instance.deleted_by == self.user for instance in self.instances)
        )

    def test_project_date_modified_updated(self):
        """Project date_modified is updated to the current time"""
        mocked_now = timezone.now()

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            delete_xform_submissions(self.xform, self.user)

        self.project.refresh_from_db()
        self.assertEqual(self.project.date_modified, mocked_now)

    @patch("onadata.libs.utils.logger_tools.send_message")
    def test_action_recorded(self, mock_send_message):
        """Action is recorded in the audit log"""
        delete_xform_submissions(self.xform, self.user, [self.instances[0].pk])

        mock_send_message.assert_called_once_with(
            instance_id=[self.instances[0].pk],
            target_id=self.xform.id,
            target_type="xform",
            user=self.user,
            message_verb="submission_deleted",
        )

    def test_hard_delete_enabled(self):
        """Hard delete should be enabled for hard delete to be successful"""
        with self.assertRaises(PermissionDenied):
            delete_xform_submissions(self.xform, self.user, soft_delete=False)

    def test_cache_deleted(self):
        """Cache tracking submissions being deleted is cleared"""
        cache.set(f"xfm-submissions-deleting-{self.xform.id}", [self.instances[0].pk])
        delete_xform_submissions(self.xform, self.user)

        self.assertIsNone(cache.get(f"xfm-submissions-deleting-{self.xform.id}"))

    def test_decrypted_submission_count_updated(self):
        """Decrypted submission count is updated"""
        self.xform.is_managed = True
        self.xform.num_of_decrypted_submissions = 4
        self.xform.save(update_fields=["num_of_decrypted_submissions", "is_managed"])
        self.xform.refresh_from_db()

        self.assertEqual(self.xform.num_of_decrypted_submissions, 4)

        delete_xform_submissions(
            self.xform, self.user, instance_ids=[self.instances[0].pk]
        )

        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_decrypted_submissions, 3)


class ResponseWithMimetypeAndNameTestCase(TestBase):
    """Tests for method `response_with_mimetype_and_name`"""

    @patch("onadata.libs.utils.logger_tools.get_storages_media_download_url")
    def test_signed_url_full_mime_type(self, mock_download_url):
        """Signed url is generated for full mime type"""
        mock_download_url.return_value = "https://test.com/test.csv"
        response = response_with_mimetype_and_name(
            "text/csv",
            "test",
            extension="csv",
            file_path="test.csv",
            full_mime=True,
            show_date=False,
        )
        self.assertEqual(response.status_code, 302)
        mock_download_url.assert_called_once_with(
            "test.csv",
            "attachment; filename=\"download.csv\"; filename*=UTF-8''test.csv",
            "text/csv",
            3600,
        )

    @patch("onadata.libs.utils.logger_tools.get_storages_media_download_url")
    def test_signed_url_no_full_mime(self, mock_download_url):
        """Signed url is generated for no full mime type"""
        mock_download_url.return_value = "https://test.com/test.csv"
        response = response_with_mimetype_and_name(
            "csv",
            "test",
            extension="csv",
            file_path="test.csv",
            full_mime=False,
            show_date=False,
        )
        self.assertEqual(response.status_code, 302)
        mock_download_url.assert_called_once_with(
            "test.csv",
            "attachment; filename=\"download.csv\"; filename*=UTF-8''test.csv",
            "application/csv",
            3600,
        )


class GetStoragesMediaDownloadUrlTestCase(TestBase):
    """Tests for method `get_storages_media_download_url`"""

    @override_settings(
        STORAGES={"default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}},
        AWS_STORAGE_BUCKET_NAME="test-bucket",
    )
    @patch("boto3.client")
    def test_s3_url(self, mock_boto_client):
        """S3 signed url is generated if default storage is S3"""
        mock_s3 = mock_boto_client.return_value
        mock_s3.generate_presigned_url.return_value = "https://test.com/test.csv"

        url = get_storages_media_download_url(
            "test.csv", 'attachment; filename="test.csv"', "text/csv", 3600
        )

        self.assertEqual(url, "https://test.com/test.csv")
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "test-bucket",
                "Key": "test.csv",
                "ResponseContentDisposition": 'attachment; filename="test.csv"',
                "ResponseContentType": "text/csv",
            },
            ExpiresIn=3600,
        )

        # Content type is application/octet-stream if not provided
        mock_s3.generate_presigned_url.reset_mock()
        url = get_storages_media_download_url(
            "test.csv", 'attachment; filename="test.csv"', expires_in=3600
        )
        self.assertEqual(url, "https://test.com/test.csv")
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "test-bucket",
                "Key": "test.csv",
                "ResponseContentDisposition": 'attachment; filename="test.csv"',
                "ResponseContentType": "application/octet-stream",
            },
            ExpiresIn=3600,
        )

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "storages.backends.azure_storage.AzureStorage"}
        },
        AZURE_ACCOUNT_NAME="test-account",
        AZURE_CONTAINER="test-container",
    )
    @patch("azure.storage.blob.generate_blob_sas")
    def test_azure_url(self, mock_generate_blob_sas):
        """Azure signed url is generated if default storage is Azure"""
        mock_generate_blob_sas.return_value = "sas-token"
        mocked_now = timezone.now()

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = mocked_now
            url = get_storages_media_download_url(
                "test.csv", 'attachment; filename="test.csv"', "text/csv", 3600
            )

        self.assertEqual(
            url,
            "https://test-account.blob.core.windows.net/test-container/test.csv?sas-token",
        )
        called_kwargs = mock_generate_blob_sas.call_args.kwargs

        self.assertEqual(called_kwargs["account_name"], "test-account")
        self.assertEqual(called_kwargs["container_name"], "test-container")
        self.assertEqual(called_kwargs["blob_name"], "test.csv")
        self.assertEqual(called_kwargs["expiry"], mocked_now + timedelta(seconds=3600))
        self.assertEqual(
            called_kwargs["content_disposition"], 'attachment; filename="test.csv"'
        )
        self.assertEqual(called_kwargs["content_type"], "text/csv")
        self.assertIsInstance(called_kwargs["permission"], AccountSasPermissions)
        self.assertTrue(called_kwargs["permission"].read)
