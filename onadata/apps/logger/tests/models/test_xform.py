# -*- coding: utf-8 -*-
"""
test_xform module
"""

import os
from builtins import str as text
from io import BytesIO
from unittest.mock import call, patch

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils import timezone

from pyxform.builder import SurveyElementBuilder as RealBuilder
from pyxform.errors import PyXFormError

from onadata.apps.logger.models import DataView, Instance, KMSKey, XForm
from onadata.apps.logger.models.kms import XFormKey
from onadata.apps.logger.models.xform import (
    DuplicateUUIDError,
    check_xform_uuid,
    get_survey_from_file_object,
)
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

    def test_update_num_of_decrypted_submissions_unmanaged(self):
        """update_num_of_decrypted_submissions() returns unmanaged form"""
        self._publish_transportation_form()
        self._make_submissions()

        result = self.xform.update_num_of_decrypted_submissions()
        self.xform.refresh_from_db()

        self.assertEqual(result, 0)
        self.assertEqual(self.xform.num_of_decrypted_submissions, 0)

    def test_update_num_of_decrypted_submissions_managed(self):
        """update_num_of_decrypted_submissions() returns for managed form

        Returns and updates the count for decrypted submissions only.
        """
        self._publish_managed_form_and_submit_instance()

        self.assertTrue(self.xform.is_managed)

        dec_instance = self._submit_decrypted_instance()

        result = self.xform.update_num_of_decrypted_submissions()
        self.xform.refresh_from_db()

        self.assertEqual(result, 1)
        self.assertEqual(self.xform.num_of_decrypted_submissions, 1)

        # Deleted Instances are excluded
        dec_instance.deleted_at = timezone.now()
        dec_instance.save()

        result = self.xform.update_num_of_decrypted_submissions()
        self.xform.refresh_from_db()

        self.assertEqual(result, 0)
        self.assertEqual(self.xform.num_of_decrypted_submissions, 0)

    def test_update_num_of_decrypted_submissions_clears_cache(self):
        """update_num_of_decrypted_submissions() clears cached count"""
        self._publish_transportation_form()

        # Simulate cached count
        cache_key = f"xfm-dec-submission-count-{self.xform.pk}"
        cache.set(cache_key, 10)

        self.xform.update_num_of_decrypted_submissions()

        self.assertIsNone(cache.get(cache_key))

    def test_live_num_of_decrypted_submissions(self):
        """Test XForm.live_num_of_decrypted_submissions"""
        self._publish_transportation_form()

        # Simulate cached count
        cache_key = f"xfm-dec-submission-count-{self.xform.pk}"
        cache.set(cache_key, 10)

        self.xform.num_of_decrypted_submissions = 5
        self.xform.save(update_fields=["num_of_decrypted_submissions"])

        self.assertEqual(self.xform.live_num_of_decrypted_submissions, 15)

    def test_num_of_pending_decryption_submissions(self):
        """Test XForm.num_of_pending_decryption_submissions"""
        self._publish_transportation_form()
        self._make_submissions()

        # Simulate cached count
        cache_key = f"xfm-dec-submission-count-{self.xform.pk}"
        cache.set(cache_key, 10)

        # num_of_submissions is greater than num_of_decrypted_submissions
        self.xform.num_of_submissions = 20
        self.xform.save(update_fields=["num_of_submissions"])

        # Simulate decrypted submissions count committed to DB
        self.xform.num_of_decrypted_submissions = 5
        self.xform.save(update_fields=["num_of_decrypted_submissions"])
        self.xform.refresh_from_db()

        self.assertEqual(self.xform.num_of_pending_decryption_submissions, 5)

        # num_of_submissions is less than num_of_decrypted_submissions
        self.xform.num_of_submissions = 5
        self.xform.save(update_fields=["num_of_submissions"])
        self.xform.refresh_from_db()

        self.assertEqual(self.xform.num_of_pending_decryption_submissions, 0)

    def test_get_media_survey_xpaths(self):
        """Test that get_media_survey_xpaths includes all media-type elements"""
        md = """
        | survey |
        |        | type            | name         | label        |
        |        | photo           | photo1       | Photo        |
        |        | audio           | audio1       | Audio        |
        |        | background-audio| bg_audio1    | Background Audio |
        |        | video           | video1       | Video        |
        |        | file            | file1        | File         |
        |        | image           | image1       | Image        |
        """

        xform = self._publish_markdown(md, self.user, id_string="media_test")
        media_xpaths = xform.get_media_survey_xpaths()

        # Verify all media types are included
        self.assertIn("photo1", media_xpaths)
        self.assertIn("audio1", media_xpaths)
        self.assertIn("bg_audio1", media_xpaths)
        self.assertIn("video1", media_xpaths)
        self.assertIn("file1", media_xpaths)
        self.assertIn("image1", media_xpaths)

        # Verify background-audio is specifically detected
        bg_audio_elements = xform.get_survey_elements_of_type("background-audio")
        self.assertEqual(len(bg_audio_elements), 1)
        self.assertEqual(bg_audio_elements[0].name, "bg_audio1")

    def test_get_survey_from_file_object_file_pointer_reset(self):
        """Test that get_survey_from_file_object resets file pointer before reading"""
        # Create a simple XLS form content
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../..",
            "fixtures",
            "tutorial",
            "tutorial.xlsx",
        )

        with open(xls_file_path, "rb") as f:
            file_content = f.read()

        # Create a BytesIO object and simulate that it has been read before
        file_object = BytesIO(file_content)
        file_object.name = "tutorial.xlsx"

        # Read some data to move the file pointer away from the beginning
        file_object.read(100)

        # Verify the file pointer is not at the beginning
        self.assertNotEqual(file_object.tell(), 0)

        # Call get_survey_from_file_object - it should work even with file pointer moved
        survey, workbook_json = get_survey_from_file_object(file_object)

        # Verify we got a valid survey object and workbook json
        self.assertIsNotNone(survey)
        self.assertTrue(hasattr(survey, "name"))
        self.assertIsNotNone(workbook_json)
        self.assertIsInstance(workbook_json, dict)

        # Test again with file pointer at arbitrary position
        file_object.seek(50)
        survey2, workbook_json2 = get_survey_from_file_object(file_object)

        # Should still work and produce the same result
        self.assertIsNotNone(survey2)
        self.assertEqual(survey.name, survey2.name)
        self.assertEqual(workbook_json["name"], workbook_json2["name"])

    def test_get_survey_fallback_on_trigger_error(self):
        """Test _get_survey falls back to XLS when trigger format error occurs."""

        self._publish_transportation_form()
        xform = XForm.objects.get(pk=self.xform.pk)

        # Store the original workbook_json for comparison
        original_workbook_json = xform.json.copy()

        # Set json to survey.to_json_dict() to simulate old format
        old_format_json = xform.survey.to_json_dict()
        XForm.objects.filter(pk=xform.pk).update(json=old_format_json)
        xform.refresh_from_db()

        # Clear cached survey
        if hasattr(xform, "_survey"):
            delattr(xform, "_survey")

        # Mock the builder to raise PyXFormError on first call only
        # Second call (from get_survey_from_file_object) should succeed
        call_count = [0]

        def side_effect_fn(json_data):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call - simulate trigger error
                raise PyXFormError(
                    "Internal error: PyXForm expected processed trigger data as a tuple, "
                    "but received a type '<class 'str'>' with value '${assessor}'."
                )
            # Subsequent calls - use real implementation
            return RealBuilder().create_survey_element_from_dict(json_data)

        with patch(
            "onadata.apps.logger.models.xform.SurveyElementBuilder"
        ) as mock_builder_class:
            mock_builder = mock_builder_class.return_value
            mock_builder.create_survey_element_from_dict.side_effect = side_effect_fn

            # Should not raise - should fall back to XLS and persist workbook_json
            survey = xform.survey
            self.assertIsNotNone(survey)

        # Verify the JSON was updated to workbook_json format (not survey.to_json_dict())
        xform.refresh_from_db()
        self.assertIsInstance(xform.json, dict)
        # The json should now be workbook_json, not the old survey.to_json_dict() format
        self.assertEqual(xform.json, original_workbook_json)

    def test_is_was_managed_when_managed(self):
        """is_was_managed returns True when is_managed is True"""
        self._publish_transportation_form()
        self.xform.is_managed = True
        self.xform.save()

        self.assertTrue(self.xform.is_was_managed)

    def test_is_was_managed_when_not_managed_no_keys(self):
        """is_was_managed returns False when not managed and no KMS keys"""
        self._publish_transportation_form()
        self.assertFalse(self.xform.is_managed)
        self.assertFalse(self.xform.kms_keys.exists())

        self.assertFalse(self.xform.is_was_managed)

    def test_is_was_managed_with_kms_keys(self):
        """is_was_managed returns True when KMS keys exist even if not managed"""
        self._publish_transportation_form()
        self.assertFalse(self.xform.is_managed)

        ct = ContentType.objects.get_for_model(XForm)
        kms_key = KMSKey.objects.create(
            key_id="test-key",
            public_key="test-public-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=ct,
            object_id=self.xform.pk,
        )
        XFormKey.objects.create(
            xform=self.xform,
            kms_key=kms_key,
            version="1",
        )

        self.assertTrue(self.xform.is_was_managed)
