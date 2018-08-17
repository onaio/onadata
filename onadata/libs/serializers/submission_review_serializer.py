"""
Submission Review Serializer Module
"""
from __future__ import unicode_literals

from rest_framework import exceptions, serializers

from onadata.apps.logger.models import SubmissionReview
from onadata.libs.serializers.note_serializer import NoteSerializer


class SubmissionReviewSerializer(serializers.ModelSerializer):
    """
    SubmissionReviewSerializer Class
    """
    note_text = serializers.CharField(source='note.note')

    class Meta:
        """
        Meta Options for SubmissionReviewSerializer
        """
        model = SubmissionReview
        fields = ('id', 'instance', 'created_by', 'status', 'date_created',
                  'note_text', 'date_modified')
        read_only_fields = ['note']

    def validate(self, attrs):
        """
        Custom Validate Method for SubmissionReviewSerializer
        """
        status = attrs.get('status')
        note_text = attrs.get('note_text')

        if status == SubmissionReview.REJECTED:
            if note_text is None:
                raise exceptions.ValidationError({
                    'note':
                    'Can\'t reject a submission without a comment.'
                })
        return attrs

    def create(self, validated_data):
        """
        Custom create method for SubmissionReviewSerializer
        """
        note_data = validated_data.pop('note')
        note_data['instance'] = validated_data.get('instance')
        note_data['created_by'] = validated_data.get('created_by')
        note_data['instance_field'] = "_review_status"

        note = NoteSerializer.create(
            NoteSerializer(), validated_data=note_data)

        validated_data['note'] = note

        return SubmissionReview.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Custom update method for SubmissionReviewSerializer
        """
        note = instance.note
        note_data = validated_data.pop('note')

        NoteSerializer().update(instance=note, validated_data=note_data)

        instance.status = validated_data.get('status', instance.status)

        instance.save()

        return instance
