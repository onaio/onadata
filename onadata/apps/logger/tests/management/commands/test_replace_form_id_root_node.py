"""
Module containing the tests for the replace_form_id_root_node
management command
"""
from io import BytesIO

from django.conf import settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.management.commands.replace_form_id_root_node \
    import replace_form_id_with_correct_root_node
from onadata.libs.utils.logger_tools import create_instance


class TestReplaceFormIDRootNodeCommand(TestBase):
    """TestReplaceFormIDRootNodeCommand Class"""

    def test_replaces_form_id_root_node(self):
        """
        Test that the command correctly replaces the form ID
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | file  | file   | File  |
        |        | image | image  | Image |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)
        id_string = xform.id_string

        xml_string = f"""
        <{id_string} id="{id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
            </meta>
            <file>Health_2011_03_13.xml_2011-03-15_20-30-28.xml</file>
            <image>1300221157303.jpg</image>
        </{id_string}>
        """
        media_root = (f'{settings.PROJECT_ROOT}/apps/logger/tests/Health'
                      '_2011_03_13.xml_2011-03-15_20-30-28/')
        image_media = django_file(
            path=f'{media_root}1300221157303.jpg', field_name='image',
            content_type='image/jpeg')
        file_media = django_file(
            path=f'{media_root}Health_2011_03_13.xml_2011-03-15_20-30-28.xml',
            field_name='file', content_type='text/xml')
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[file_media, image_media])

        # Attempt replacement of root node name
        replace_form_id_with_correct_root_node(
            inst_id=instance.id, root='data', commit=True)
        instance.refresh_from_db()

        expected_xml = f"""<data id="{id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
            </meta>
            <file>Health_2011_03_13.xml_2011-03-15_20-30-28.xml</file>
            <image>1300221157303.jpg</image>
        </data>"""
        self.assertEqual(instance.xml, expected_xml)
