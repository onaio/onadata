from __future__ import absolute_import

from onadata.apps.logger.models import XForm
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

    def test_deleted_twin_ignored(self):
        """The active form with the id_string is used when a deleted twin exists"""
        id_string = "x" * 95
        md = """
        | survey |
        |        | type              | name   | label   |
        |        | select one fruits | fruit  | Fruit   |
        | choices |
        |         | list name         | name   | label  |
        |         | fruits            | orange | Orange |
        """
        dd = self._publish_markdown(md, self.user, id_string=id_string)
        deleted_xform = XForm.objects.get(pk=dd.pk)
        deleted_xform.soft_delete(self.user)
        self._publish_markdown(md, self.user, id_string=id_string)

        result = response_for_text(self.user.username, "test allo", id_string=id_string)

        self.assertEqual(result["code"], SMS_SUBMISSION_REFUSED)

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
