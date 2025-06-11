# -*- coding: utf-8 -*-
"""
Test logger_tools utility functions.
"""

import json
import os
import re
from collections import OrderedDict
from io import BytesIO
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models.signals import post_save
from django.http.request import HttpRequest
from django.test.utils import override_settings
from django.utils import timezone

from defusedxml.ElementTree import ParseError

from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.models import Instance
from onadata.apps.logger.xform_instance_parser import AttachmentNameError
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.test_utils.pyxform_test_case import PyxformTestCase
from onadata.libs.utils.common_tags import MEDIA_ALL_RECEIVED, MEDIA_COUNT, TOTAL_MEDIA
from onadata.libs.utils.logger_tools import (
    create_instance,
    delete_xform_submissions,
    generate_content_disposition_header,
    get_first_record,
    reconstruct_xform_export_register,
    register_instance_repeat_columns,
    safe_create_instance,
)
from onadata.libs.utils.user_auth import get_user_default_project


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

    def test_get_first_record(self):
        """
        Test get_first_record() function.
        """
        xform_md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | text  | name   | Photo |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(xform_md, self.user)

        self.assertIsNone(get_first_record(Instance.objects.all().only("id")))

        xml_string = f"""
        <data id="{xform.id_string}">
            <name>Alice</name>
        </data>
        """
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[],
        )
        record = get_first_record(Instance.objects.all().only("id"))
        self.assertIsNotNone(record)
        self.assertEqual(record.id, instance.id)

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


class RegisterInstanceRepeatColumnsTestCase(TestBase):
    """Tests for method `register_instance_repeat_columns`"""

    def setUp(self):
        super().setUp()

        # Disable signals
        post_save.disconnect(
            sender=Instance, dispatch_uid="register_instance_repeat_columns"
        )

        self.project = get_user_default_project(self.user)
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
        self.xform = self._publish_markdown(md, self.user, self.project)
        self.xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            f"<formhub><uuid>{self.xform.uuid}</uuid></formhub>"
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
        self.instance = Instance.objects.create(
            xml=self.xml, user=self.user, xform=self.xform
        )
        self.register = MetaData.objects.get(
            data_type="export_columns_register",
            object_id=self.xform.pk,
            content_type=ContentType.objects.get_for_model(self.xform),
        )

    def test_columns_added(self):
        """Incoming columns are added to the register"""
        merged_multiples = json.loads(
            self.register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples = json.loads(
            self.register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        # Before Instance repeat columns are added
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
        self.assertEqual(merged_multiples, expected_columns)
        self.assertEqual(split_multiples, expected_columns)

        register_instance_repeat_columns(self.instance)

        # After Instance repeat columns are added
        self.register.refresh_from_db()
        merged_multiples = json.loads(
            self.register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples = json.loads(
            self.register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
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

        self.assertEqual(merged_multiples, expected_columns)
        self.assertEqual(split_multiples, expected_columns)

    def test_register_not_found(self):
        """Nothing happens if export columns register is not found"""
        self.register.delete()
        register_instance_repeat_columns(self.instance)

        exists = MetaData.objects.filter(data_type="export_columns_register").exists()
        self.assertFalse(exists)

    def test_select_multiples(self):
        """Columns for a form with select multiples are added"""
        md = """
        | survey |
        |        | type                     | name         | label        |
        |        | text                     | name         | Name         |
        |        | integer                  | age          | Age          |
        |        | begin repeat             | browser_use  | Browser Use  |
        |        | integer                  | year         | Year         |
        |        | select_multiple browsers | browsers     | Browsers     |
        |        | end repeat               |              |              |

        | choices |
        |         | list name | name    | label             |
        |         | browsers  | firefox | Firefox           |
        |         | browsers  | chrome  | Chrome            |
        |         | browsers  | ie      | Internet Explorer |
        |         | browsers  | safari  | Safari            |
        """
        xform = self._publish_markdown(
            md, self.user, self.project, id_string="browser_use"
        )
        register = MetaData.objects.get(
            data_type="export_columns_register",
            object_id=xform.pk,
            content_type=ContentType.objects.get_for_model(xform),
        )
        # Before Instance repeat columns are added
        merged_multiples_columns = json.loads(
            register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        expected_columns = OrderedDict(
            [
                ("name", None),
                ("age", None),
                ("browser_use", []),
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
            "<name>John Doe</name>"
            "<age>25</age>"
            "<browser_use>"
            "<year>2021</year>"
            "<browsers>firefox chrome</browsers>"
            "</browser_use>"
            "<meta>"
            "<instanceID>uuid:cea7954a-60d5-4f40-b844-080733a74a34</instanceID>"
            "</meta>"
            "</data>"
        )
        instance = Instance.objects.create(xml=xml, user=self.user, xform=xform)

        register_instance_repeat_columns(instance)

        # After Instance repeat columns are added
        register.refresh_from_db()
        merged_multiples_columns = json.loads(
            register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )

        self.assertEqual(
            split_multiples_columns,
            OrderedDict(
                [
                    ("name", None),
                    ("age", None),
                    (
                        "browser_use",
                        [
                            "browser_use[1]/year",
                            "browser_use[1]/browsers/firefox",
                            "browser_use[1]/browsers/chrome",
                            "browser_use[1]/browsers/ie",
                            "browser_use[1]/browsers/safari",
                        ],
                    ),
                    ("meta/instanceID", None),
                ]
            ),
        )
        self.assertEqual(
            merged_multiples_columns,
            OrderedDict(
                [
                    ("name", None),
                    ("age", None),
                    ("browser_use", ["browser_use[1]/year", "browser_use[1]/browsers"]),
                    ("meta/instanceID", None),
                ]
            ),
        )


class ReconstructXFormExportRegisterTestCase(TestBase):
    """Tests for method `reconstruct_xform_export_register`"""

    def setUp(self):
        super().setUp()

        # Disable signals
        post_save.disconnect(
            sender=Instance, dispatch_uid="register_instance_repeat_columns"
        )

        self.project = get_user_default_project(self.user)
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
        self.xform = self._publish_markdown(md, self.user, self.project)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            f"<formhub><uuid>{self.xform.uuid}</uuid></formhub>"
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
        self.instance = Instance.objects.create(
            xml=xml, user=self.user, xform=self.xform
        )
        self.register = MetaData.objects.get(
            data_type="export_columns_register",
            object_id=self.xform.pk,
            content_type=ContentType.objects.get_for_model(self.xform),
        )
        self.expected_columns = OrderedDict(
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

    def test_register(self):
        """Repeats from all instances are registered"""
        merged_multiples_columns = json.loads(
            self.register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            self.register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        # Before reconstructing export columns register
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

        reconstruct_xform_export_register(self.xform)

        # After reconstructing register
        self.register.refresh_from_db()
        merged_multiples_columns = json.loads(
            self.register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples_columns = json.loads(
            self.register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )

        self.assertEqual(merged_multiples_columns, self.expected_columns)
        self.assertEqual(split_multiples_columns, self.expected_columns)

    def test_register_not_found(self):
        """Nothing happens if register not found"""
        self.register.delete()

        reconstruct_xform_export_register(self.xform)
