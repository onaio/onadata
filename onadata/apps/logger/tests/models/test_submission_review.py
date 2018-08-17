"""
Submission Review Model Tests Module
"""
from __future__ import unicode_literals

from onadata.apps.logger.models import Instance, Note, SubmissionReview
from onadata.apps.main.tests.test_base import TestBase


class TestSubmissionReview(TestBase):
    """
    TestSubmissionReview Class
    """

    def test_note_text_property_method(self):
        """
        Test :
            - note_text property
            - get_note_text method
        """
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        note = Note(
            instance=instance,
            note='Hey there',
            instance_field="",
        )

        submission_review = SubmissionReview(instance=instance)

        # Returns None if Submission_Review has no note_text
        self.assertIsNone(submission_review.get_note_text())
        self.assertIsNone(submission_review.note_text)

        submission_review = SubmissionReview(instance=instance, note=note)

        # Returns correct note text when note is present
        self.assertEqual(note.note, submission_review.get_note_text())
        self.assertEqual(note.note, submission_review.note_text)
