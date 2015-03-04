from onadata.apps.main.tests.test_base import TestBase
from datetime import date, datetime


class TestExportTools(TestBase):

    def test_invalid_date_format_is_caught(self):
        from onadata.libs.utils.export_tools import encode_if_str
        row = {"date": date(0201, 9, 9)}
        with self.assertRaises(Exception) as error:
            encode_if_str(row, "date", True)

        self.assertEqual(error.exception.message,
                         u'0129-09-09 has an invalid date format')

        row = {"date": date(2001, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, '2001-09-09')

    def test_invalid_datetime_format_is_caught(self):
        from onadata.libs.utils.export_tools import encode_if_str
        row = {"datetime": datetime(0201, 9, 9)}
        with self.assertRaises(Exception) as error:
            encode_if_str(row, "datetime", True)

        self.assertEqual(error.exception.message,
                         u'0129-09-09 00:00:00 has an invalid datetime format')

        row = {"datetime": datetime(2001, 9, 9)}
        date_str = encode_if_str(row, "datetime", True)
        self.assertEqual(date_str, '2001-09-09T00:00:00')
