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