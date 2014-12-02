import os

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm, Instance


class TestXForm(TestBase):
    def test_submission_count_filters_deleted(self):
        self._publish_transportation_form_and_submit_instance()

        # update the xform object the num_submissions seems to be cached in
        # the in-memory xform object as zero
        self.xform = XForm.objects.get(pk=self.xform.id)
        self.assertEqual(self.xform.submission_count(), 1)
        instance = Instance.objects.get(xform=self.xform)
        instance.set_deleted()
        self.assertIsNotNone(instance.deleted_at)

        # update the xform object, the num_submissions seems to be cached in
        # the in-memory xform object as one
        self.xform = XForm.objects.get(pk=self.xform.id)
        self.assertEqual(self.xform.submission_count(), 0)

    def test_set_title_in_xml_unicode_error(self):
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../..",  "fixtures", "tutorial", "tutorial_arabic_labels.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        self.assertTrue(isinstance(self.xform.xml, unicode))

        # change title
        self.xform.title = u'Random Title'

        self.assertNotIn(self.xform.title, self.xform.xml)

        # convert xml to str
        self.xform.xml = self.xform.xml.encode('utf-8')
        self.assertTrue(isinstance(self.xform.xml, str))

        # set title in xform xml
        self.xform._set_title()
        self.assertIn(self.xform.title, self.xform.xml)

    def test_version_length(self):
        """Test Xform.version can store more than 12 chars"""
        self._publish_transportation_form_and_submit_instance()
        xform = XForm.objects.get(pk=self.xform.id)
        xform.version = u'12345678901234567890'
        xform.save()

        self.assertTrue(len(xform.version) > 12)
