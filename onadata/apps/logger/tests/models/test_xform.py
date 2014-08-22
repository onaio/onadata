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

        # convert xml to str
        self.xform.xml = self.xform.xml.encode('utf-8')
        self.assertTrue(isinstance(self.xform.xml, str))

        # change title
        self.xform.title = u'Random Title'

        with self.assertRaises(UnicodeDecodeError):
            # set title in xform xml
            self.xform._set_title()
