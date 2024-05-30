# -*- coding: utf-8 -*-
"""
Test logger_tools utility functions.
"""
import os
import re
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http.request import HttpRequest

from defusedxml.ElementTree import ParseError

from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.models import Instance, Entity, RegistrationForm
from onadata.apps.logger.xform_instance_parser import AttachmentNameError
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.test_utils.pyxform_test_case import PyxformTestCase
from onadata.libs.utils.common_tags import MEDIA_ALL_RECEIVED, MEDIA_COUNT, TOTAL_MEDIA
from onadata.libs.utils.logger_tools import (
    create_entity_from_instance,
    create_instance,
    generate_content_disposition_header,
    get_first_record,
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


class CreateEntityTestCase(TestBase):
    """Tests for method `create_entity`"""

    def setUp(self):
        super().setUp()
        # Mute signal that creates Entity when Instance is saved
        self._mute_post_save_signals([(Instance, "create_entity")])
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
        self.instance = Instance.objects.create(
            xml=self.xml,
            user=self.user,
            xform=self.xform,
            version=self.xform.version,
        )
        self.registration_form = RegistrationForm.objects.first()

    def test_entity_created(self):
        """Entity is created successfully"""
        create_entity_from_instance(self.instance, self.registration_form)
        entity = Entity.objects.first()
        self.assertEqual(entity.registration_form, self.registration_form)
        self.assertEqual(entity.instance, self.instance)
        self.assertEqual(entity.xml, self.xml)
        expected_json = {
            "formhub/uuid": "d156a2dce4c34751af57f21ef5c4e6cc",
            "geometry": "-1.286905 36.772845 0 0",
            "species": "purpleheart",
            "circumference_cm": 300,
            "meta/instanceID": "uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b",
            "meta/instanceName": "300cm purpleheart",
            "meta/entity/label": "300cm purpleheart",
            "_xform_id_string": "trees_registration",
            "_version": "2022110901",
            "_id": entity.pk,
        }
        self.assertCountEqual(entity.json, expected_json)
        self.assertEqual(entity.uuid, "dbee4c32-a922-451c-9df7-42f40bf78f48")
        entity_list = self.registration_form.entity_list
        entity_list.refresh_from_db()
        self.assertEqual(entity_list.num_entities, 1)
        self.assertEqual(entity_list.last_entity_update_time, entity.date_modified)
