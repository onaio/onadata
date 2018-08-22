# -*- coding: utf-8 -*-
"""
Submission Review Serializer Test Module
"""
from __future__ import unicode_literals

from rest_framework.exceptions import ValidationError

from onadata.apps.logger.models import Instance, Note, SubmissionReview
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.serializers.submission_review_serializer import \
    SubmissionReviewSerializer
from onadata.libs.utils.common_tags import (COMMENT_REQUIRED,
                                            SUBMISSION_REVIEW_INSTANCE_FIELD)


class TestSubmissionReviewSerializer(TestBase):
    """
    TestSubmissionReviewSerializer Class
    """

    def _create_submission_review(self):
        """
        Utility to create a submission review
        """

        self._publish_transportation_form_and_submit_instance()

        instance = Instance.objects.first()

        data = {
            "instance": instance.id,
            "note": "Hey there",
            "status": SubmissionReview.APPROVED
        }

        serializer_instance = SubmissionReviewSerializer(data=data)
        self.assertFalse(Note.objects.filter(instance=instance).exists())

        self.assertTrue(serializer_instance.is_valid())

        submission_review = serializer_instance.save()

        # Creates Note Object
        self.assertTrue(Note.objects.filter(instance=instance).exists())

        note = submission_review.note
        self.assertEqual(instance, submission_review.instance)
        self.assertEqual("Hey there", submission_review.note_text)
        self.assertEqual(SUBMISSION_REVIEW_INSTANCE_FIELD, note.instance_field)
        self.assertEqual(note.instance, submission_review.instance)

        return serializer_instance.data

    def test_validate_bad_data(self):
        """
        Test:
            - Rejects Rejected Submission Reviews with no comments
        """

        self._publish_transportation_form_and_submit_instance()

        instance = Instance.objects.first()

        data = {"instance": instance.id, "status": SubmissionReview.REJECTED}

        with self.assertRaises(ValidationError) as no_comment:
            SubmissionReviewSerializer().validate(data)

            no_comment_error_detail = no_comment.exception.detail['note']
            self.assertEqual(COMMENT_REQUIRED, no_comment_error_detail)

    def test_submission_review_create(self):
        """
        Test:
            - Can create a Submission Review
        """
        serializer_instance = self._create_submission_review()

        expected_fields = [
            'id', 'instance', 'created_by', 'status', 'date_created',
            'date_modified', 'note'
        ]

        self.assertEqual(set(expected_fields), set(list(serializer_instance)))

    def test_submission_review_update(self):
        """
        Test:
            - We can update a submission review
            - Updating a Submission Review Doesnt Create
              a new Note
        """
        data = self._create_submission_review()
        submission_review = SubmissionReview.objects.first()
        old_note_text = submission_review.note_text

        data['note'] = "Goodbye"

        self.assertEqual(len(Note.objects.all()), 1)
        serializer_instance = SubmissionReviewSerializer(
            instance=submission_review, data=data)
        self.assertTrue(serializer_instance.is_valid())
        new_review = serializer_instance.save()

        # Doesnt create a new note
        self.assertEqual(len(Note.objects.all()), 1)
        self.assertNotEqual(old_note_text, new_review.note_text)
