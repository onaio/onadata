import os
import sys

from django.core.management import call_command
from django.core.management.base import CommandError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.common_tools import report_exception


class TestPublishXLS(TestBase):

    def test_publish_xls(self):
        xls_file_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.xls")
        count = XForm.objects.count()
        call_command('publish_xls', xls_file_path, self.user.username)
        self.assertEqual(XForm.objects.count(), count + 1)
        form = XForm.objects.get()
        self.assertFalse(form.require_auth)

    def test_publish_xls_replacement(self):
        count = XForm.objects.count()
        xls_file_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.xls")
        call_command('publish_xls', xls_file_path, self.user.username)
        self.assertEqual(XForm.objects.count(), count + 1)
        count = XForm.objects.count()
        xls_file_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation_updated.xls")
        # call command without replace param
        with self.assertRaises(CommandError):
            call_command('publish_xls', xls_file_path, self.user.username)
        # now we call the command with the replace param
        call_command(
            'publish_xls', xls_file_path, self.user.username, replace=True)
        # count should remain the same
        self.assertEqual(XForm.objects.count(), count)
        # check if the extra field has been added
        self.xform = XForm.objects.order_by('id').reverse()[0]
        is_updated_form = len([e.name for e in self.xform.survey_elements
                               if e.name == u'preferred_means']) > 0
        self.assertTrue(is_updated_form)

    def test_report_exception_with_exc_info(self):
        e = Exception("A test exception")
        try:
            raise e
        except Exception as e:
            exc_info = sys.exc_info()
            try:
                report_exception(subject="Test report exception", info=e,
                                 exc_info=exc_info)
            except Exception as e:
                raise AssertionError("%s" % e)

    def test_report_exception_without_exc_info(self):
        e = Exception("A test exception")
        try:
            report_exception(subject="Test report exception", info=e)
        except Exception as e:
            raise AssertionError("%s" % e)

    def test_publish_xls_version(self):
        xls_file_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.xls")
        count = XForm.objects.count()
        call_command('publish_xls', xls_file_path, self.user.username)
        self.assertEqual(XForm.objects.count(), count + 1)
        form = XForm.objects.get()
        self.assertIsNotNone(form.version)
