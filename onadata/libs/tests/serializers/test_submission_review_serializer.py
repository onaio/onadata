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


class TestSubmissionReviewSerializer(TestBase):
    """
    TestSubmissionReviewSerializer Class
    """

    def test_validate_bad_data(self):
        """
        Test:
            - Rejects Rejected Submission Reviews with no comments
        """

        self._publish_transportation_form_and_submit_instance()

        instance = Instance.objects.first()

        data = {
            "instance": instance.id,
            "status": SubmissionReview.REJECTED
        }

        with self.assertRaises(ValidationError) as no_comment:
            SubmissionReviewSerializer().validate(data)

        no_comment_error_detail = no_comment.exception.detail['note']
        self.assertEqual(
            no_comment_error_detail,
            'Can\'t reject a submission without a comment.'
        )

    def test_submission_review_create(self):
        """
        Test:
            - Can create a Submission Review
        """
        self._publish_transportation_form_and_submit_instance()

        instance = Instance.objects.first()
        note = Note(
            instance=instance,
            instance_field="",
            created_by=None,
            note='Hey there.'
        )

        note.save()

        data = {
            "instance": instance.id,
            "note": note.id,
            "status": SubmissionReview.APPROVED
        }

        serializer_instance = SubmissionReviewSerializer(data=data)

        self.assertTrue(serializer_instance.is_valid())

        submission_review = serializer_instance.save()

        self.assertEqual(instance, submission_review.instance)
        self.assertEqual(note, submission_review.note)
        self.assertEqual(note.note, submission_review.note_text)

        expected_fields = [
            'id',
            'instance',
            'note',
            'created_by',
            'status',
            'date_created',
            'date_modified',
            'note_text'
        ]

        self.assertEqual(
            set(expected_fields),
            set(list(serializer_instance.data)))
