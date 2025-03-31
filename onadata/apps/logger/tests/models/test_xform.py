# -*- coding: utf-8 -*-
"""
test_xform module
"""

import os
from builtins import str as text
from unittest.mock import call, patch

from onadata.apps.logger.models import DataView, Instance, XForm
from onadata.apps.logger.models.xform import DuplicateUUIDError, check_xform_uuid
from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.common_tools import get_abbreviated_xpath


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
            "../..",
            "fixtures",
            "tutorial",
            "tutorial_arabic_labels.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        self.assertTrue(isinstance(self.xform.xml, str))

        # change title
        self.xform.title = "Random Title"

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
        xform.version = "12345678901234567890"
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
        xform.title = "Trial & Error"

        xform.soft_delete(self.user)
        xform.refresh_from_db()

        # deleted_at is not None
        self.assertIsNotNone(xform.deleted_at)

        # is inactive, no submissions will be allowed
        self.assertFalse(xform.downloadable)

        # deleted-at suffix is present
        self.assertIn("-deleted-at-", xform.id_string)
        self.assertIn("-deleted-at-", xform.sms_id_string)
        self.assertEqual(xform.deleted_by.username, "bob")

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
        kwargs = {"name": "favs", "title": "Fruits", "id_string": "favs"}
        survey = self.md_to_pyxform_survey(markdown_xlsform, kwargs)
        xform = XForm()
        xform._survey = survey  # pylint: disable=W0212

        # non existent field
        self.assertIsNone(xform.get_survey_element("non_existent"))

        # get fruita element by name
        fruita = xform.get_survey_element("fruita")
        self.assertEqual(get_abbreviated_xpath(fruita.get_xpath()), "a/fruita")
        self.assertEqual(xform.get_child_elements("NoneExistent"), [])

    def test_check_xform_uuid(self):
        """
        Test check_xform_uuid(new_uuid).
        """
        self._publish_transportation_form()
        with self.assertRaises(DuplicateUUIDError):
            check_xform_uuid(self.xform.uuid)

        # soft delete xform
        self.xform.soft_delete()

        try:
            check_xform_uuid(self.xform.uuid)
        except DuplicateUUIDError as e:
            self.fail("DuplicateUUIDError raised: %s" % e)

    def test_id_string_max_length_on_soft_delete(self):
        """
        Test XForm soft delete with long id_string or sms_id_string
        """
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)
        new_string = (
            "transportation_twenty_fifth_july_two_thousand_and_"
            "eleven_test_for_long_sms_id_string_and_id_string"
        )
        xform.id_string = new_string
        xform.sms_id_string = new_string

        # deleted_at is None
        self.assertIsNone(xform.deleted_at)

        # deleted-at suffix not present
        self.assertNotIn("-deleted-at-", xform.id_string)
        self.assertNotIn("-deleted-at-", xform.sms_id_string)

        # '&' should raise an XLSFormError exception when being changed, for
        # deletions this should not raise any exception however
        xform.title = "Trial & Error"

        xform.soft_delete(self.user)
        xform.refresh_from_db()

        d_id_string = new_string + xform.deleted_at.strftime("-deleted-at-%s")
        d_sms_id_string = new_string + xform.deleted_at.strftime("-deleted-at-%s")

        # deleted_at is not None
        self.assertIsNotNone(xform.deleted_at)

        # is inactive, no submissions will be allowed
        self.assertFalse(xform.downloadable)

        self.assertGreater(len(d_sms_id_string), 100)
        self.assertGreater(len(d_id_string), 100)
        self.assertIn(xform.sms_id_string, d_id_string)
        self.assertIn(xform.sms_id_string, d_sms_id_string)
        self.assertEqual(xform.id_string, d_id_string[:100])
        self.assertEqual(xform.sms_id_string, d_sms_id_string[:100])
        self.assertEqual(xform.deleted_by.username, "bob")

    def test_id_string_length(self):
        """Test Xform.id_string cannot store more than 100 chars"""
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)
        new_string = (
            "transportation_twenty_fifth_july_two_thousand_and_"
            "eleven_test_for_long_sms_id_string_and_id_string_"
            "before_save"
        )
        xform.id_string = new_string
        xform.sms_id_string = new_string

        with self.assertRaises(XLSFormError):
            xform.save()

    def test_multiple_model_nodes(self):
        """
        Test XForm.set_uuid_in_xml() function is able to handle
        a form that has field named model which may match the XForm's
        top level node also named model.
        """
        md = """
        | survey  |
        |         | type              | name  | label   |
        |         | select one fruits | fruit | Fruit   |
        |         | text              | model | Model   |
        | choices |
        |         | list name         | name   | label  |
        |         | fruits            | orange | Orange |
        |         | fruits            | mango  | Mango  |
        """
        dd = self._publish_markdown(md, self.user, id_string="a")
        self.assertNotIn(
            "<formhub>\n            <uuid/>\n          </formhub>\n", dd.xml
        )
        dd.set_uuid_in_xml()
        self.assertIn("<formhub>\n            <uuid/>\n          </formhub>\n", dd.xml)

    @patch("onadata.apps.logger.models.xform.clear_project_cache")
    def test_restore_deleted(self, mock_clear_project_cache):
        """Deleted XForm can be restored"""
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)
        # Create dataview for form
        data_view = DataView.objects.create(
            name="test_view",
            project=self.project,
            xform=xform,
            columns=["name", "age"],
        )
        # Create metadata for form
        metadata = xform.metadata_set.create(
            data_value="test",
            data_type="test",
            data_file="test",
            data_file_type="test",
        )
        xform.soft_delete(self.user)
        xform.refresh_from_db()
        data_view.refresh_from_db()
        metadata.refresh_from_db()

        # deleted_at is not None
        self.assertIsNotNone(xform.deleted_at)
        self.assertIsNotNone(data_view.deleted_at)
        self.assertIsNotNone(metadata.deleted_at)

        # is inactive, no submissions will be allowed
        self.assertFalse(xform.downloadable)

        # deleted-at suffix is present
        self.assertIn("-deleted-at-", xform.id_string)
        self.assertIn("-deleted-at-", xform.sms_id_string)
        self.assertEqual(xform.deleted_by.username, "bob")
        calls = [call(self.project.pk), call(self.project.pk)]
        mock_clear_project_cache.has_calls(calls, any_order=True)
        mock_clear_project_cache.reset_mock()

        xform.restore()
        xform.refresh_from_db()
        data_view.refresh_from_db()
        metadata.refresh_from_db()

        # deleted_at is None
        self.assertIsNone(xform.deleted_at)
        self.assertIsNone(data_view.deleted_at)
        self.assertIsNone(metadata.deleted_at)

        # is active
        self.assertTrue(xform.downloadable)

        # deleted-at suffix not present
        self.assertNotIn("-deleted-at-", xform.id_string)
        self.assertNotIn("-deleted-at-", xform.sms_id_string)
        self.assertIsNone(xform.deleted_by)
        calls = [call(self.project.pk), call(self.project.pk)]
        mock_clear_project_cache.has_calls(calls, any_order=True)

    @patch("onadata.apps.logger.models.xform.clear_project_cache")
    def test_restore_deleted_merged_xform(self, mock_clear_project_cache):
        """Deleted merged XForm can be restored"""
        merged_xf = self._create_merged_dataset()
        xform = XForm.objects.get(pk=merged_xf.pk)

        xform.soft_delete(self.user)
        xform.refresh_from_db()
        merged_xf.refresh_from_db()

        # deleted_at is not None
        self.assertIsNotNone(xform.deleted_at)
        self.assertIsNotNone(merged_xf.deleted_at)

        # is inactive, no submissions will be allowed
        self.assertFalse(xform.downloadable)

        # deleted-at suffix is present
        self.assertIn("-deleted-at-", xform.id_string)
        self.assertIn("-deleted-at-", xform.sms_id_string)
        self.assertEqual(xform.deleted_by.username, "bob")
        calls = [call(self.project.pk), call(self.project.pk)]
        mock_clear_project_cache.has_calls(calls, any_order=True)
        mock_clear_project_cache.reset_mock()

        xform.restore()
        xform.refresh_from_db()
        merged_xf.refresh_from_db()

        # deleted_at is None
        self.assertIsNone(xform.deleted_at)
        self.assertIsNone(merged_xf.deleted_at)

        # is active
        self.assertTrue(xform.downloadable)

        # deleted-at suffix not present
        self.assertNotIn("-deleted-at-", xform.id_string)
        self.assertNotIn("-deleted-at-", xform.sms_id_string)
        self.assertIsNone(xform.deleted_by)
        calls = [call(self.project.pk), call(self.project.pk)]
        mock_clear_project_cache.has_calls(calls, any_order=True)
