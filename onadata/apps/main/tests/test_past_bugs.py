import os
from builtins import str
from pyxform.errors import PyXFormError

from onadata.apps.logger.models import XForm, Instance
from onadata.apps.main.tests.test_base import TestBase


class TestInputs(TestBase):
    """
    This is where I'll input all files that proved problematic for
    users when uploading.
    """

    def test_uniqueness_of_group_names_enforced(self):
        """
        Test an error is raised when a form containing a group
        with the name "data" is present within the form.

        This error is raised due to the fact that the root node
        is named "data"
        """
        pre_count = XForm.objects.count()
        self._create_user_and_login()
        expected_message = (
            "The name 'data' is the same as the form name. Use a "
            "different section name (or change the form name in "
            "the 'name' column of the settings sheet)."
        )
        self.assertRaisesMessage(
            PyXFormError,
            expected_message,
            self._publish_xls_file,
            "fixtures/group_names_must_be_unique.xlsx",
        )
        self.assertEqual(XForm.objects.count(), pre_count)

    def test_mch(self):
        msg = "Unknown question type 'Select one from source'"
        with self.assertRaisesMessage(PyXFormError, msg):
            self._publish_xls_file("fixtures/bug_fixes/MCH_v1.xlsx")

    def test_erics_files(self):
        for name in [
            "battery_life.xlsx",
            "enumerator_weekly.xlsx",
            "Enumerator_Training_Practice_Survey.xlsx",
        ]:
            try:
                self._publish_xls_file(os.path.join("fixtures", "bug_fixes", name))
            except Exception as e:
                self.assertEqual("Duplicate column header: label", str(e))


class TestSubmissionBugs(TestBase):
    def test_submission_with_mixed_case_username(self):
        self._publish_transportation_form()
        s = self.surveys[0]
        count = Instance.objects.count()
        self._make_submission(
            os.path.join(
                self.this_directory,
                "fixtures",
                "transportation",
                "instances",
                s,
                s + ".xml",
            ),
            "BoB",
        )
        self.assertEqual(Instance.objects.count(), count + 1)


class TestCascading(TestBase):
    def test_correct_id_string_picked(self):
        XForm.objects.all().delete()
        name = "new_cascading_select.xlsx"
        id_string = "cascading_select_test"
        self._publish_xls_file(
            os.path.join(self.this_directory, "fixtures", "bug_fixes", name)
        )
        self.assertEqual(XForm.objects.count(), 1)
        xform_id_string = XForm.objects.all()[0].id_string
        self.assertEqual(xform_id_string, id_string)
