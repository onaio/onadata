# -*- coding: utf-8 -*-
"""
MergedXFormSerializer class
"""

import base64
import uuid

from django.utils.translation import ugettext as _
from rest_framework import serializers

from onadata.apps.logger.models import MergedXForm, XForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH
from pyxform.builder import create_survey_element_from_json


def minimum_two_xforms(value):
    """Validate at least 2 xforms are provided"""
    if len(value) < 2:
        raise serializers.ValidationError(
            _('This field should have at least two unique xforms.'))

    if len(set(value)) != len(value):
        raise serializers.ValidationError(
            _('This field should have unique xforms'))

    return value


class MergedXFormSerializer(serializers.HyperlinkedModelSerializer):
    """MergedXForm Serializer to create and update merged datasets"""
    url = serializers.HyperlinkedIdentityField(
        view_name='merged-xform-detail', lookup_field='pk')
    name = serializers.CharField(
        max_length=XFORM_TITLE_LENGTH, write_only=True)
    xforms = serializers.ManyRelatedField(
        allow_empty=False,
        child_relation=serializers.HyperlinkedRelatedField(
            allow_empty=False,
            queryset=XForm.objects.filter(is_merged_dataset=False),
            view_name='xform-detail'),
        validators=[minimum_two_xforms])
    num_of_submissions = serializers.ReadOnlyField(
        source='number_of_submissions')

    class Meta:
        model = MergedXForm
        fields = ('url', 'id', 'xforms', 'name', 'project', 'title',
                  'num_of_submissions')
        read_only_fields = ('num_of_submissions',)

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

        return super(MergedXFormSerializer, self).create(validated_data)
