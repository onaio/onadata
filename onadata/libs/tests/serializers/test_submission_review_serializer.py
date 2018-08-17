# -*- coding: utf-8 -*-
"""
Submission Review Serializer Test Module
"""
from __future__ import unicode_literals

from rest_framework.exceptions import ValidationError

from onadata.apps.logger.models import Instance, SubmissionReview
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
