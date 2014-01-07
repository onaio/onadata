from test_base_sms import TestBaseSMS
from onadata.apps.sms_support.tools import SMS_SUBMISSION_REFUSED


class TestNotAllowed(TestBaseSMS):

    def setUp(self):
        TestBaseSMS.setUp(self)
        self.setup_form(allow_sms=False)

    def test_refused_not_enabled(self):
        # SMS submissions not allowed
        result = self.response_for_text(self.username, 'test allo')
        self.assertEqual(result['code'], SMS_SUBMISSION_REFUSED)

    def test_allow_sms(self):
        result = self.response_for_text(self.username,
                                        'test +a 1 y 1950-02-22 john doe')
        self.assertEqual(result['code'], SMS_SUBMISSION_REFUSED)
        self.assertEqual(result.get('id'), None)
