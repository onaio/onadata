"""
Submission Review Serializer Module
"""
from __future__ import unicode_literals

from rest_framework import exceptions, serializers

from onadata.apps.logger.models import Note, SubmissionReview
from onadata.libs.utils.common_tags import (COMMENT_REQUIRED,
                                            SUBMISSION_REVIEW_INSTANCE_FIELD)


class SubmissionReviewSerializer(serializers.ModelSerializer):
    """
    SubmissionReviewSerializer Class
    """
    note = serializers.CharField(source='note.note', required=False)

    class Meta:
        """
        Meta Options for SubmissionReviewSerializer
        """
        model = SubmissionReview
        fields = ('id', 'instance', 'created_by', 'status', 'date_created',
                  'note', 'date_modified')

    def validate(self, attrs):
        """
        Custom Validate Method for SubmissionReviewSerializer
        """
        status = attrs.get('status')
        note = attrs.get('note')

        if status == SubmissionReview.REJECTED and not note:
            raise exceptions.ValidationError({'note': COMMENT_REQUIRED})
        return attrs

    def create(self, validated_data):
        """
        Custom create method for SubmissionReviewSerializer
        """
        request = self.context.get('request')

        if request:
            validated_data['created_by'] = request.user

        if 'note' in validated_data:
            note_data = validated_data.pop('note')
            note_data['instance'] = validated_data.get('instance')
            note_data['created_by'] = validated_data.get('created_by')
            note_data['instance_field'] = SUBMISSION_REVIEW_INSTANCE_FIELD

            note = Note.objects.create(**note_data)
            validated_data['note'] = note

        return SubmissionReview.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Custom update method for SubmissionReviewSerializer
        """
        note = instance.note
        note_data = validated_data.pop('note')

        note.note = note_data['note']
        note.save()

        instance.status = validated_data.get('status', instance.status)

        instance.save()

        return instance
