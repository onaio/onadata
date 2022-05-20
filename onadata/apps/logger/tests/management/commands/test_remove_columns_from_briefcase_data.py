"""
Module containing the tests for the remove_columns_from_briefcase_data
management command
"""
from io import BytesIO

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.management.commands.remove_columns_from_briefcase_data import (
    remove_columns_from_xml,
)
from onadata.libs.utils.logger_tools import create_instance


class TestRemoveColumnsFromBriefcaseDataCommand(TestBase):
    def test_removes_correct_columns(self):
        """
        Test that the command returns the XML without the specified
        columns
        """
        md = """
        | survey |
        |        | type   | name       | label            |
        |        | text   | first_name | Enter first name |
        |        | text   | comment    | Enter a comment  |
        |        | image  | photo      | Take a selfie    |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)
        id_string = xform.id_string

        xml_string = f"""
        <{id_string} id="{id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
            </meta>
            <first_name>Davis</first_name>
            <comment>I love coding!</comment>
            <photo>face.jpg</photo>
        </{id_string}>
        """
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode("utf-8")),
            media_files=[],
        )

        expected_xml = (
            f'<{id_string} id="{id_string}"><meta>'
            "<instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>"
            "</meta><comment>I love coding!</comment>"
            f"</{id_string}>"
        )
        modified_xml = remove_columns_from_xml(instance.xml, ["first_name", "photo"])
        self.assertEqual(modified_xml, expected_xml)
