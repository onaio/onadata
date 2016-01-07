import re

from onadata.libs.utils.logger_tools import generate_content_disposition_header
from onadata.apps.main.tests.test_base import TestBase


class TestLoggerTools(TestBase):
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
        self.assertTrue(re.search(file_name_with_timestamp_pattern,
                                  return_value_with_name_and_no_show_date))

        return_value_with_name_and_false_show_date = \
            generate_content_disposition_header(file_name, extension, False)
        print return_value_with_name_and_false_show_date
        self.assertTrue(re.search(file_name_pattern,
                                  return_value_with_name_and_false_show_date))
