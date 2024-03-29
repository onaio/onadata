from __future__ import absolute_import

from onadata.apps.sms_support.tests.test_base_sms import TestBaseSMS, response_for_text
from onadata.apps.sms_support.tools import (
    SMS_API_ERROR,
    SMS_PARSING_ERROR,
    SMS_SUBMISSION_ACCEPTED,
    SMS_SUBMISSION_REFUSED,
)


class TestParser(TestBaseSMS):
    def setUp(self):
        TestBaseSMS.setUp(self)
        self.setup_form(allow_sms=True)

    def test_api_error(self):
        # missing identity or text
        result = response_for_text(self.username, "hello", identity="")
        self.assertEqual(result["code"], SMS_API_ERROR)

        result = response_for_text(self.username, text="")
        self.assertEqual(result["code"], SMS_API_ERROR)

    def test_invalid_syntax(self):
        # invalid text message
        result = response_for_text(self.username, "hello")
        self.assertEqual(result["code"], SMS_PARSING_ERROR)

    def test_invalid_group(self):
        # invalid text message
        result = response_for_text(self.username, "++a 20", id_string=self.id_string)
        self.assertEqual(result["code"], SMS_PARSING_ERROR)

    def test_refused_with_keyword(self):
        # submission has proper keywrd with invalid text
        result = response_for_text(self.username, "test allo")
        self.assertEqual(result["code"], SMS_PARSING_ERROR)

    def test_sucessful_submission(self):
        result = response_for_text(self.username, "test +a 1 y 1950-02-22 john doe")
        self.assertEqual(result["code"], SMS_SUBMISSION_ACCEPTED)
        self.assertTrue(result["id"])

    def test_invalid_type(self):
        result = response_for_text(self.username, "test +a yes y 1950-02-22 john doe")
        self.assertEqual(result["code"], SMS_PARSING_ERROR)

    def test_missing_required_field(self):
        # required field name missing
        result = response_for_text(self.username, "test +b ff")
        self.assertEqual(result["code"], SMS_SUBMISSION_REFUSED)
