# -*- coding: utf-8 -*-
"""
Test logger_tools utility functions.
"""

import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from datetime import timezone as tz
from io import BytesIO
from unittest.mock import Mock, call, patch

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
from onadata.apps.logger.models import (Entity, EntityList, Instance,
                                        RegistrationForm, SurveyType, XForm)
from onadata.apps.logger.xform_instance_parser import AttachmentNameError
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.test_utils.pyxform_test_case import PyxformTestCase
from onadata.libs.utils.common_tags import (MEDIA_ALL_RECEIVED, MEDIA_COUNT,
                                            TOTAL_MEDIA)
from onadata.libs.utils.logger_tools import (
    commit_cached_elist_num_entities, create_entity_from_instance,
    create_instance, dec_elist_num_entities, delete_xform_submissions,
    generate_content_disposition_header, get_first_record,
    inc_elist_num_entities, reconstruct_xform_export_register,
    register_instance_repeat_columns, safe_create_instance)
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


class CreateEntityFromInstanceTestCase(TestBase):
    """Tests for method `create_entity_from_instance`"""

    def setUp(self):
        super().setUp()
        self.xform = self._publish_registration_form(self.user)
        self.xml = (
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
        self.survey_type = SurveyType.objects.create(slug="slug-foo")
        instance = Instance(
            xform=self.xform,
            xml=self.xml,
            version=self.xform.version,
            survey_type=self.survey_type,
        )
        # We use bulk_create to avoid calling create_entity signal
        Instance.objects.bulk_create([instance])
        self.instance = Instance.objects.first()
        self.registration_form = RegistrationForm.objects.first()
        self.entity_list = EntityList.objects.get(name="trees")

    def test_entity_created(self):
        """Entity is created successfully"""
        create_entity_from_instance(self.instance, self.registration_form)

        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        entity_list = self.registration_form.entity_list
        entity_list.refresh_from_db()

        self.assertEqual(entity.entity_list, entity_list)

        expected_json = {
            "geometry": "-1.286905 36.772845 0 0",
            "species": "purpleheart",
            "circumference_cm": 300,
            "label": "300cm purpleheart",
        }

        self.assertCountEqual(entity.json, expected_json)
        self.assertEqual(str(entity.uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")

        self.assertEqual(cache.get(f"elist-num-entities-{entity_list.pk}"), 1)
        self.assertEqual(entity_list.last_entity_update_time, entity.date_modified)
        self.assertEqual(entity.history.count(), 1)

        entity_history = entity.history.first()

        self.assertEqual(entity_history.registration_form, self.registration_form)
        self.assertEqual(entity_history.instance, self.instance)
        self.assertEqual(entity_history.xml, self.instance.xml)
        self.assertEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, self.xform.version)
        self.assertEqual(entity_history.created_by, self.instance.user)

    def test_grouped_section(self):
        """Entity properties within grouped section"""
        group_md = """
        | survey |
        |         | type        | name     | label        | save_to |
        |         | begin group | tree     | Tree         |         |
        |         | geopoint    | location | Location     | geometry|
        |         | text        | species  | Species      | species |
        |         | end group   |          |              |         |
        | settings|             |          |              |         |
        |         | form_title  | form_id  | instance_name| version |
        |         | Group       | group    | ${species}   | 2022110901|
        | entities| list_name   | label    |              |         |
        |         | trees       | ${species}|             |         |
        """
        self._publish_markdown(group_md, self.user, self.project, id_string="group")
        xform = XForm.objects.get(id_string="group")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="group" version="2022110901">'
            "<formhub><uuid>9833e23e6c6147298e0ae2d691dc1e6f</uuid></formhub>"
            "<tree>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "</tree>"
            "<meta>"
            "<instanceID>uuid:b817c598-a215-4fa9-ba78-a7c738bd1f91</instanceID>"
            "<instanceName>purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="47e335da-46ce-4151-9898-7ed1d54778c6">'
            "<label>purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        instance = Instance(
            xform=xform,
            xml=xml,
            version=xform.version,
            survey_type=self.survey_type,
        )
        # We use bulk_create to avoid calling create_entity signal
        Instance.objects.bulk_create([instance])
        instance = Instance.objects.order_by("pk").last()
        registration_form = RegistrationForm.objects.get(
            xform=xform, entity_list=self.entity_list
        )
        create_entity_from_instance(instance, registration_form)
        entity = Entity.objects.first()
        expected_json = {
            "geometry": "-1.286905 36.772845 0 0",
            "species": "purpleheart",
            "label": "purpleheart",
        }

        self.assertEqual(Entity.objects.count(), 1)
        self.assertCountEqual(entity.json, expected_json)


class EntityListNumEntitiesBase(TestBase):
    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(
            name="trees", project=self.project, num_entities=10
        )
        self.ids_key = "elist-num-entities-ids"
        self.lock_key = f"{self.ids_key}-lock"
        self.counter_key_prefix = "elist-num-entities-"
        self.counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        self.created_at_key = "elist-num-entities-ids-created-at"

    def tearDown(self) -> None:
        super().tearDown()

        cache.clear()


class IncEListNumEntitiesTestCase(EntityListNumEntitiesBase):
    """Tests for method `inc_elist_num_entities`"""

    def test_cache_locked(self):
        """Database counter is incremented if cache is locked"""
        cache.set(self.lock_key, "true")
        cache.set(self.counter_key, 3)
        inc_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 11)
        # Cached counter should not be updated
        self.assertEqual(cache.get(self.counter_key), 3)

    @patch("django.utils.timezone.now")
    def test_cache_unlocked(self, mock_now):
        """Cache counter is incremented if cache is unlocked"""
        mocked_now = datetime(2024, 7, 26, 12, 45, 0, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.created_at_key))

        inc_elist_num_entities(self.entity_list.pk)

        self.assertEqual(cache.get(self.counter_key), 1)
        self.assertEqual(cache.get(self.ids_key), {self.entity_list.pk})
        self.assertEqual(cache.get(self.created_at_key), mocked_now)
        self.entity_list.refresh_from_db()
        # Database counter should not be updated
        self.assertEqual(self.entity_list.num_entities, 10)
        # New EntityList
        vaccine = EntityList.objects.create(name="vaccine", project=self.project)
        inc_elist_num_entities(vaccine.pk)

        self.assertEqual(cache.get(f"{self.counter_key_prefix}{vaccine.pk}"), 1)
        self.assertEqual(cache.get(self.ids_key), {self.entity_list.pk, vaccine.pk})
        vaccine.refresh_from_db()
        self.assertEqual(vaccine.num_entities, 0)

        # Database counter incremented if cache inacessible
        with patch(
            "onadata.libs.utils.logger_tools._inc_elist_num_entities_cache"
        ) as mock_inc:
            with patch("onadata.libs.utils.logger_tools.logger.exception") as mock_exc:
                mock_inc.side_effect = ConnectionError
                cache.set(self.counter_key, 3)
                inc_elist_num_entities(self.entity_list.pk)
                self.entity_list.refresh_from_db()

                self.assertEqual(cache.get(self.counter_key), 3)
                self.assertEqual(self.entity_list.num_entities, 11)
                mock_exc.assert_called_once()

    @patch("django.utils.timezone.now")
    @patch.object(cache, "set")
    @patch.object(cache, "add")
    def test_cache_no_expire(self, mock_cache_add, mock_cache_set, mock_now):
        """Cached counter does not expire

        Clean up should be done periodically such as in a background task
        """
        mocked_now = datetime(2024, 7, 26, 12, 45, 0, tzinfo=tz.utc)
        mock_now.return_value = mocked_now
        inc_elist_num_entities(self.entity_list.pk)

        # Timeout should be `None`
        self.assertTrue(
            call(self.counter_key, 1, None) in mock_cache_add.call_args_list
        )
        self.assertTrue(
            call(self.created_at_key, mocked_now, None) in mock_cache_add.call_args_list
        )
        mock_cache_set.assert_called_once_with(
            self.ids_key, {self.entity_list.pk}, None
        )

    def test_time_cache_set_once(self):
        """The cached time of creation is set once"""
        now = timezone.now()
        cache.set(self.created_at_key, now)

        inc_elist_num_entities(self.entity_list.pk)
        # Cache value is not overridden
        self.assertEqual(cache.get(self.created_at_key), now)

    @override_settings(ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT=3)
    @patch("onadata.libs.utils.logger_tools.report_exception")
    def test_failover(self, mock_report_exc):
        """Failover is executed if commit timeout threshold exceeded"""
        cache_created_at = timezone.now() - timedelta(minutes=10)
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, cache_created_at)
        cache.set(self.ids_key, {self.entity_list.pk})

        inc_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 14)
        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.created_at_key))
        subject = "Periodic task not running"
        task_name = "onadata.apps.logger.tasks.commit_cached_elist_num_entities_async"
        msg = (
            f"The failover has been executed because task {task_name} "
            "is not configured or has malfunctioned"
        )
        mock_report_exc.assert_called_once_with(subject, msg)
        self.assertEqual(cache.get("elist-failover-report-sent"), "sent")

    @override_settings(ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT=3)
    @patch("onadata.libs.utils.logger_tools.report_exception")
    def test_failover_report_cache_hit(self, mock_report_exc):
        """Report exception not sent if cache `elist-failover-report-sent` set"""
        cache.set("elist-failover-report-sent", "sent")
        cache_created_at = timezone.now() - timedelta(minutes=10)
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, cache_created_at)
        cache.set(self.ids_key, {self.entity_list.pk})

        inc_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 14)
        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.created_at_key))
        mock_report_exc.assert_not_called()


class DecEListNumEntitiesTestCase(EntityListNumEntitiesBase):
    """Tests for method `dec_elist_num_entities`"""

    def test_cache_locked(self):
        """Database counter is decremented if cache is locked"""
        counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        cache.set(self.lock_key, "true")
        cache.set(counter_key, 3)
        dec_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 9)
        # Cached counter should not be updated
        self.assertEqual(cache.get(counter_key), 3)

    def test_cache_unlocked(self):
        """Cache counter is decremented if cache is unlocked"""
        counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        cache.set(counter_key, 3)
        dec_elist_num_entities(self.entity_list.pk)

        self.assertEqual(cache.get(counter_key), 2)
        self.entity_list.refresh_from_db()
        # Database counter should not be updated
        self.assertEqual(self.entity_list.num_entities, 10)

        # Database counter is decremented if cache missing
        cache.delete(counter_key)
        dec_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()
        self.assertEqual(self.entity_list.num_entities, 9)

        # Database counter is decremented if cache inaccesible
        with patch(
            "onadata.libs.utils.logger_tools._dec_elist_num_entities_cache"
        ) as mock_dec:
            with patch("onadata.libs.utils.logger_tools.logger.exception") as mock_exc:
                mock_dec.side_effect = ConnectionError
                cache.set(counter_key, 3)
                dec_elist_num_entities(self.entity_list.pk)
                self.entity_list.refresh_from_db()

                self.assertEqual(cache.get(counter_key), 3)
                self.assertEqual(self.entity_list.num_entities, 8)
                mock_exc.assert_called_once()


class CommitCachedEListNumEntitiesTestCase(EntityListNumEntitiesBase):
    """Tests for method `commit_cached_elist_num_entities`"""

    def test_counter_commited(self):
        """Cached counter is commited in the database"""
        cache.set(self.ids_key, {self.entity_list.pk})
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, timezone.now())
        commit_cached_elist_num_entities()
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 13)
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.created_at_key))

    def test_cache_empty(self):
        """Empty cache is handled appropriately"""
        commit_cached_elist_num_entities()
        self.entity_list.refresh_from_db()
        self.assertEqual(self.entity_list.num_entities, 10)

    def test_lock_already_acquired(self):
        """Commit unsuccessful if lock is already acquired"""
        cache.set(self.lock_key, "true")
        cache.set(self.ids_key, {self.entity_list.pk})
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, timezone.now())
        commit_cached_elist_num_entities()
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 10)
        self.assertIsNotNone(cache.get(self.lock_key))
        self.assertIsNotNone(cache.get(self.ids_key))
        self.assertIsNotNone(cache.get(self.counter_key))
        self.assertIsNotNone(cache.get(self.created_at_key))


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
