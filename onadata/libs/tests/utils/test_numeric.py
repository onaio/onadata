from unittest import TestCase
from onadata.libs.utils.numeric import int_or_parse_error
from rest_framework.exceptions import ParseError


class TestNumeric(TestCase):
    def test_int_or_parse_error_with_url(self):
        url = "http://api.ona.iovrocndwm.detectify.io"
        with self.assertRaises(ParseError) as err:
            int_or_parse_error(url, u"Invalid value for formid %s.")

        self.assertEqual(
            err.exception.args[0],
            ('Invalid value for formid '
             'http%3A//api.ona.iovrocndwm.detectify.io.')
        )

    def test_int_or_parse_error_with_html_str(self):
        html_str = "<p>thisishtml<p>"
        with self.assertRaises(ParseError) as err:
            int_or_parse_error(html_str, u"Invalid value for formid %s.")

        self.assertEqual(
            err.exception.args[0],
            ('Invalid value for formid '
             '&lt;p&gt;thisishtml&lt;p&gt;.')
        )
