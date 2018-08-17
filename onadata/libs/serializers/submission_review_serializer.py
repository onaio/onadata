"""
Submission Review Serializer Module
"""
from __future__ import unicode_literals

from rest_framework import exceptions, serializers

from onadata.apps.logger.models import SubmissionReview


class SubmissionReviewSerializer(serializers.ModelSerializer):
    """
    SubmissionReviewSerializer Class
    """

    class Meta:
        """
        Meta Options for SubmissionReviewSerializer
        """
        model = SubmissionReview
        fields = (
            'id',
            'instance',
            'note',
            'created_by',
            'status',
            'date_created',
            'date_modified')
        read_only_fields = ['note_text']

    def validate(self, attrs):
        """
        Custom Validate Method for SubmissionReviewSerializer
        """
        status = attrs.get('status')
        note = attrs.get('note')

        if status == SubmissionReview.REJECTED:
            if note is None:
                raise exceptions.ValidationError(
                    {'note': 'Can\'t reject a submission without a comment.'}
                )
        return attrs
