# -*- coding: utf-8 -*-
"""
test_xform module
"""
import os
from builtins import str as text
from past.builtins import basestring

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm, Instance


class TestXForm(TestBase):
    """
    Test XForm model.
    """
    def test_submission_count(self):
        """
        Test submission count does not include deleted submissions.
        """
        self._publish_transportation_form_and_submit_instance()

        # update the xform object the num_submissions seems to be cached in
        # the in-memory xform object as zero
        xform = XForm.objects.get(pk=self.xform.id)
        self.assertEqual(xform.submission_count(), 1)
        instance = Instance.objects.get(xform=self.xform)
        instance.set_deleted()
        self.assertIsNotNone(instance.deleted_at)

        # update the xform object, the num_submissions seems to be cached in
        # the in-memory xform object as one
        xform = XForm.objects.get(pk=self.xform.id)
        self.assertEqual(xform.submission_count(), 0)

    def test_set_title_unicode_error(self):
        """
        Test title in xml does not error on unicode title.
        """
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../..", "fixtures", "tutorial", "tutorial_arabic_labels.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        self.assertTrue(isinstance(self.xform.xml, basestring))

        # change title
        self.xform.title = u'Random Title'

        self.assertNotIn(self.xform.title, self.xform.xml)

        # convert xml to str
        self.assertTrue(isinstance(self.xform.xml, text))

        # set title in xform xml
        self.xform._set_title()  # pylint: disable=W0212
        self.assertIn(self.xform.title, self.xform.xml)

    def test_version_length(self):
        """Test Xform.version can store more than 12 chars"""
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)
        xform.version = u'12345678901234567890'
        xform.save()

        self.assertTrue(len(xform.version) > 12)

    def test_soft_delete(self):
        """
        Test XForm soft delete.
        """
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)

        # deleted_at is None
        self.assertIsNone(xform.deleted_at)

        # is active
        self.assertTrue(xform.downloadable)

        # deleted-at suffix not present
        self.assertNotIn("-deleted-at-", xform.id_string)
        self.assertNotIn("-deleted-at-", xform.sms_id_string)

        # '&' should raise an XLSFormError exception when being changed, for
        # deletions this should not raise any exception however
        xform.title = 'Trial & Error'

        xform.soft_delete(self.user)
        xform.refresh_from_db()

        # deleted_at is not None
        self.assertIsNotNone(xform.deleted_at)

        # is inactive, no submissions will be allowed
        self.assertFalse(xform.downloadable)

        # deleted-at suffix is present
        self.assertIn("-deleted-at-", xform.id_string)
        self.assertIn("-deleted-at-", xform.sms_id_string)
        self.assertEqual(xform.deleted_by.username, 'bob')

    def test_get_survey_element(self):
        """
        Test XForm.get_survey_element()
        """
        markdown_xlsform = """
        | survey |
        |        | type                   | name   | label   |
        |        | begin group            | a      | Group A |
        |        | select one fruits      | fruita | Fruit A |
        |        | select one fruity      | fruity | Fruit Y |
        |        | end group              |        |         |
        |        | begin group            | b      | Group B |
        |        | select one fruits      | fruitz | Fruit Z |
        |        | select_multiple fruity | fruitb | Fruit B |
        |        | end group              |        |         |
        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        |         | fruity    | orange | Orange |
        |         | fruity    | mango  | Mango  |
        """
        kwargs = {'name': 'favs', 'title': 'Fruits', 'id_string': 'favs'}
        survey = self.md_to_pyxform_survey(markdown_xlsform, kwargs)
        xform = XForm()
        xform._survey = survey  # pylint: disable=W0212

        # non existent field
        self.assertIsNone(xform.get_survey_element("non_existent"))

        # get fruita element by name
        fruita = xform.get_survey_element('fruita')
        self.assertEqual(fruita.get_abbreviated_xpath(), "a/fruita")

        # get exact choices element from choice abbreviated xpath
        fruita_o = xform.get_survey_element("a/fruita/orange")
        self.assertEqual(fruita_o.get_abbreviated_xpath(), "a/fruita/orange")

        fruity_m = xform.get_survey_element("a/fruity/mango")
        self.assertEqual(fruity_m.get_abbreviated_xpath(), "a/fruity/mango")

        fruitb_o = xform.get_survey_element("b/fruitb/orange")
        self.assertEqual(fruitb_o.get_abbreviated_xpath(), "b/fruitb/orange")

        self.assertEqual(xform.get_child_elements('NoneExistent'), [])
