import re
from io import BytesIO

from django.conf import settings

from pyxform.tests_v1.pyxform_test_case import PyxformTestCase

from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.models import Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.common_tags import (MEDIA_ALL_RECEIVED, MEDIA_COUNT,
                                            TOTAL_MEDIA)
from onadata.libs.utils.logger_tools import (
    create_instance, generate_content_disposition_header, get_first_record)


class TestLoggerTools(PyxformTestCase, TestBase):
    def test_generate_content_disposition_header(self):
        file_name = "export"
        extension = "ext"

        date_pattern = "\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}"
        file_name_pattern = "%s.%s" % (file_name, extension)
        file_name_with_timestamp_pattern = \
            "%s-%s.%s" % (file_name, date_pattern, extension)
        return_value_with_no_name = \
            generate_content_disposition_header(None, extension)
        self.assertEquals(return_value_with_no_name, "attachment;")

        return_value_with_name_and_no_show_date = \
            generate_content_disposition_header(file_name, extension)
        self.assertTrue(
            re.search(file_name_with_timestamp_pattern,
                      return_value_with_name_and_no_show_date))

        return_value_with_name_and_false_show_date = \
            generate_content_disposition_header(file_name, extension, False)
        self.assertTrue(
            re.search(file_name_pattern,
                      return_value_with_name_and_false_show_date))

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
        self.xform = self._publish_markdown(md, self.user)

        xml_string = """
        <data id="{}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """.format(self.xform.id_string)
        file_path = "{}/apps/logger/tests/Health_2011_03_13."\
                    "xml_2011-03-15_20-30-28/1300221157303"\
                    ".jpg".format(settings.PROJECT_ROOT)
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg")
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media_file])
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance.json[MEDIA_COUNT], 1)
        self.assertEquals(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEquals(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEquals(instance.json[MEDIA_ALL_RECEIVED],
                          instance.media_all_received)
        file2_path = "{}/apps/logger/tests/Water_2011_03_17_2011-03-17_16-29"\
                     "-59/1300375832136.jpg".format(settings.PROJECT_ROOT)
        media2_file = django_file(
            path=file2_path, field_name="image2", content_type="image/jpeg")
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media2_file])
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance2.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance2.json[MEDIA_COUNT], 2)
        self.assertEquals(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEquals(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEquals(instance2.json[MEDIA_ALL_RECEIVED],
                          instance2.media_all_received)
        media2_file = django_file(
            path=file2_path, field_name="image2", content_type="image/jpeg")
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media2_file])
        instance3 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance3.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance3.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance3.json[MEDIA_COUNT], 2)
        self.assertEquals(instance3.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEquals(instance3.json[MEDIA_COUNT], instance2.media_count)
        self.assertEquals(instance3.json[MEDIA_ALL_RECEIVED],
                          instance3.media_all_received)

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
        self.xform = self._publish_markdown(md, self.user)

        xml_string = """
        <data id="{}">
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
        """.format(self.xform.id_string)
        file_path = "{}/apps/logger/tests/Health_2011_03_13."\
                    "xml_2011-03-15_20-30-28/1300221157303"\
                    ".jpg".format(settings.PROJECT_ROOT)
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg")
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media_file])
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance.json[MEDIA_COUNT], 1)
        self.assertEquals(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEquals(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEquals(instance.json[MEDIA_ALL_RECEIVED],
                          instance.media_all_received)
        file2_path = "{}/apps/logger/tests/Water_2011_03_17_2011-03-17_16-29"\
                     "-59/1300375832136.jpg".format(settings.PROJECT_ROOT)
        media2_file = django_file(
            path=file2_path, field_name="image1", content_type="image/jpeg")
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media2_file])
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance2.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance2.json[MEDIA_COUNT], 2)
        self.assertEquals(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEquals(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEquals(instance2.json[MEDIA_ALL_RECEIVED],
                          instance2.media_all_received)

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
        self.xform = self._publish_markdown(md, self.user)

        xml_string = """
        <data id="{}">
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
        """.format(self.xform.id_string)
        file_path = "{}/apps/logger/tests/Health_2011_03_13."\
                    "xml_2011-03-15_20-30-28/1300221157303"\
                    ".jpg".format(settings.PROJECT_ROOT)
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg")
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media_file])
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance.json[MEDIA_COUNT], 1)
        self.assertEquals(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEquals(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEquals(instance.json[MEDIA_ALL_RECEIVED],
                          instance.media_all_received)
        file2_path = "{}/apps/logger/tests/Water_2011_03_17_2011-03-17_16-29"\
                     "-59/1300375832136.jpg".format(settings.PROJECT_ROOT)
        media2_file = django_file(
            path=file2_path, field_name="image1", content_type="image/jpeg")
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media2_file])
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertTrue(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance2.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance2.json[MEDIA_COUNT], 2)
        self.assertEquals(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEquals(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEquals(instance2.json[MEDIA_ALL_RECEIVED],
                          instance2.media_all_received)

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
        self.xform = self._publish_markdown(md, self.user)

        xml_string = """
        <data id="{}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """.format(self.xform.id_string)
        file_path = "{}/apps/logger/tests/Health_2011_03_13."\
                    "xml_2011-03-15_20-30-28/1300221157303"\
                    ".jpg".format(settings.PROJECT_ROOT)
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg")
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media_file])
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance.json[MEDIA_COUNT], 1)
        self.assertEquals(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEquals(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEquals(instance.json[MEDIA_ALL_RECEIVED],
                          instance.media_all_received)
        media2_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg")
        create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media2_file])
        instance2 = Instance.objects.get(pk=instance.pk)
        self.assertFalse(instance2.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance2.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance2.json[MEDIA_COUNT], 1)
        self.assertEquals(instance2.json[TOTAL_MEDIA], instance2.total_media)
        self.assertEquals(instance2.json[MEDIA_COUNT], instance2.media_count)
        self.assertEquals(instance2.json[MEDIA_ALL_RECEIVED],
                          instance2.media_all_received)

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
        self.xform = self._publish_markdown(md, self.user)

        xml_string = """
        <data id="{}">
            <meta>
                <instanceID>uuid:UJ5jSMAJ1Jz4EszdgHy8n851AsKaqBPO5</instanceID>
            </meta>
            <image1>1300221157303.jpg</image1>
            <image2>1300375832136.jpg</image2>
        </data>
        """.format(self.xform.id_string)
        file_path = "{}/apps/logger/tests/Health_2011_03_13."\
                    "xml_2011-03-15_20-30-28/1300221157303"\
                    ".jpg".format(settings.PROJECT_ROOT)
        file2_path = "{}/libs/tests/utils/fixtures/tutorial/instances/uuid1/"\
                     "1442323232322.jpg".format(settings.PROJECT_ROOT)
        media_file = django_file(
            path=file_path, field_name="image1", content_type="image/jpeg")
        media2_file = django_file(
            path=file2_path, field_name="image1", content_type="image/jpeg")
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[media_file, media2_file])
        self.assertFalse(instance.json[MEDIA_ALL_RECEIVED])
        self.assertEquals(instance.json[TOTAL_MEDIA], 2)
        self.assertEquals(instance.json[MEDIA_COUNT], 1)
        self.assertEquals(instance.json[TOTAL_MEDIA], instance.total_media)
        self.assertEquals(instance.json[MEDIA_COUNT], instance.media_count)
        self.assertEquals(instance.json[MEDIA_ALL_RECEIVED],
                          instance.media_all_received)

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

        self.assertIsNone(get_first_record(Instance.objects.all().only('id')))

        xml_string = """
        <data id="{}">
            <name>Alice</name>
        </data>
        """.format(xform.id_string)
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[])
        record = get_first_record(Instance.objects.all().only('id'))
        self.assertIsNotNone(record)
        self.assertEqual(record.id, instance.id)
