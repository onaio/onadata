from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import RequestFactory

from onadata.libs.utils.log import audit_log, Actions
from onadata.apps.main.models import AuditLog


class TestAuditLog(TestCase):
    def test_audit_log_call(self):
        account_user = User(username="alice")
        request_user = User(username="bob")
        request = RequestFactory().get("/")
        # create a log
        audit = {}
        audit_log(Actions.FORM_PUBLISHED, request_user, account_user,
                  "Form published", audit, request)
        # function should just run without exception so we are good at this
        # point query for this log entry
        sort = {"created_on": -1}
        cursor = AuditLog.query_mongo(
            account_user.username, None, None, sort, 0, 1)
        self.assertTrue(cursor.count() > 0)
        record = cursor.next()
        self.assertEqual(record['account'], "alice")
        self.assertEqual(record['user'], "bob")
        self.assertEqual(record['action'], Actions.FORM_PUBLISHED)
