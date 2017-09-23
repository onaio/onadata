import os
import sys

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from onadata.apps.main.models import UserProfile
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

    def test_xform_hash(self):
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | image | image1 | Photo |
        """
        self._create_user_and_login()
        self.xform = self._publish_markdown(md, self.user)
        # make sure the has is created and is not empty
        self.assertFalse(self.xform.hash == "" or self.xform.hash is None)
        self.assertEqual(self.xform.hash, self.xform.get_hash())
        old_hash = self.xform.hash
        # publish a second form
        md2 = """
        | survey |                        |          |           |
        |        | type                   | name     | label     |
        |        | select_multiple yes_no | expensed | Expensed? |

        | choices |           |      |       |
        |         | list name | name | label |
        |         | yes_no    | 1    | Yes   |
        |         | yes_no    | 09   | No    |
        """
        self.new_user = User.objects.create(username='mosh')
        self.new_profile = UserProfile.objects.create(user=self.new_user)
        self.xform2 = self._publish_markdown(md2, self.new_user)
        # chane the xml value of form1
        self.xform.xml = self.xform2.xml
        self.xform.save()
        # assert that the hash has been updated and is not empty
        self.assertFalse(self.xform.hash == "" or self.xform.hash is None)
        self.assertFalse(self.xform.hash == old_hash)

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
