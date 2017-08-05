# -*- coding: utf-8 -*-
"""
MergedXFormSerializer class
"""

import base64
import uuid

from django.utils.translation import ugettext as _
from pyxform.builder import create_survey_element_from_json
from rest_framework import serializers

from onadata.apps.logger.models import MergedXForm, XForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH


def minimum_two_xforms(value):
    """Validate at least 2 xforms are provided"""
    if len(value) < 2:
        raise serializers.ValidationError(
            _('This field should have at least two unique xforms.'))

    if len(set(value)) != len(value):
        raise serializers.ValidationError(
            _('This field should have unique xforms'))

    return value


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    """XFormSerializer"""

    url = serializers.HyperlinkedIdentityField(
        view_name='xform-detail', lookup_field='pk')
    owner = serializers.CharField(source='user.username')
    project_name = serializers.CharField(source='project.name')

    class Meta:
        model = XForm
        fields = ('url', 'id', 'id_string', 'title', 'num_of_submissions',
                  'owner', 'project_id', 'project_name')


class XFormListField(serializers.ManyRelatedField):
    """XFormSerializer"""

    def to_representation(self, iterable):
        return [
            dict(i)
            for i in XFormSerializer(
                iterable, many=True, context=self.context).data
        ]


class MergedXFormSerializer(serializers.HyperlinkedModelSerializer):
    """MergedXForm Serializer to create and update merged datasets"""
    url = serializers.HyperlinkedIdentityField(
        view_name='merged-xform-detail', lookup_field='pk')
    name = serializers.CharField(
        max_length=XFORM_TITLE_LENGTH, write_only=True)
    xforms = XFormListField(
        allow_empty=False,
        child_relation=serializers.HyperlinkedRelatedField(
            allow_empty=False,
            queryset=XForm.objects.filter(is_merged_dataset=False),
            view_name='xform-detail'),
        validators=[minimum_two_xforms])
    num_of_submissions = serializers.SerializerMethodField()
    last_submission_time = serializers.SerializerMethodField()

    class Meta:
        model = MergedXForm
        fields = ('url', 'id', 'xforms', 'name', 'project', 'title',
                  'num_of_submissions', 'last_submission_time')

    # pylint: disable=no-self-use
    def get_num_of_submissions(self, obj):
        """Return number of submissions either from the aggregate
        'number_of_submissions' in the queryset or from the xform field
        'num_of_submissions'.
        """

        value = getattr(obj, 'number_of_submissions', obj.num_of_submissions)

        return value

    def get_last_submission_time(self, obj):
        """Return datetime of last submission from all forms"""
        values = [
            x.last_submission_time
            for x in obj.xforms.only('last_submission_time')
            if x.last_submission_time
        ]
        if values:
            return sorted(values, reverse=True)[0]

    def create(self, validated_data):
        # we get the xml and json from the first xforms
        xform = validated_data['xforms'][0]

        request = self.context['request']

        # create merged xml, json with non conflicting id_string
        survey = create_survey_element_from_json(xform.json)
        survey['id_string'] = base64.b64encode(uuid.uuid4().hex[:6])
        survey['sms_keyword'] = survey['id_string']
        survey['title'] = validated_data.pop('name')
        validated_data['json'] = survey.to_json()
        validated_data['xml'] = survey.to_xml()
        validated_data['user'] = validated_data['project'].user
        validated_data['created_by'] = request.user
        validated_data['is_merged_dataset'] = True
        validated_data['num_of_submissions'] = sum(
            [__.num_of_submissions for __ in validated_data.get('xforms')])
        validated_data['instances_with_geopoints'] = any([
            __.instances_with_geopoints for __ in validated_data.get('xforms')
        ])

        return super(MergedXFormSerializer, self).create(validated_data)
