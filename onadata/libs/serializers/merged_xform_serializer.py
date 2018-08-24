# -*- coding: utf-8 -*-
"""
MergedXFormSerializer class
"""

import base64
import json
import uuid

from django.db import transaction
from django.utils.translation import ugettext as _
from rest_framework import serializers

from pyxform.builder import create_survey_element_from_dict
from pyxform.errors import PyXFormError

from onadata.apps.logger.models import MergedXForm, XForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH
from onadata.libs.utils.common_tags import MULTIPLE_SELECT_TYPE, SELECT_ONE

SELECTS = [SELECT_ONE, MULTIPLE_SELECT_TYPE]


def _get_fields_set(xform):
    return [(element.get_abbreviated_xpath(), element.type)
            for element in xform.survey_elements
            if element.type not in ['', 'survey']]


def _get_elements(elements, intersect, parent_prefix=None):
    new_elements = []

    for element in elements:
        name = element['name']
        name = name if not parent_prefix else '/'.join([parent_prefix, name])
        if name in intersect:
            k = element.copy()
            if 'children' in element and element['type'] not in SELECTS:
                k['children'] = _get_elements(
                    element['children'],
                    [__ for __ in intersect if __.startswith(name)], name)
                if not k['children']:
                    continue
            new_elements.append(k)

    return new_elements


def get_merged_xform_survey(xforms):
    """
    Genertates a new pyxform survey object from the intersection of fields of
    the xforms being merged.

    :param xforms: A list of XForms of at least length 2.
    """
    if len(xforms) < 2:
        raise serializers.ValidationError(_('Expecting at least 2 xforms'))

    xform_sets = [_get_fields_set(xform) for xform in xforms]

    merged_xform_dict = json.loads(xforms[0].json)
    children = merged_xform_dict.pop('children')
    merged_xform_dict['children'] = []

    intersect = set(xform_sets[0]).intersection(*xform_sets[1:])
    intersect = set([__ for (__, ___) in intersect])

    merged_xform_dict['children'] = _get_elements(children, intersect)

    if '_xpath' in merged_xform_dict:
        del merged_xform_dict['_xpath']

    is_empty = True
    for child in merged_xform_dict['children']:
        if child['name'] != 'meta' and is_empty:
            is_empty = False

    if is_empty:
        raise serializers.ValidationError(_("No matching fields in xforms."))

    return create_survey_element_from_dict(merged_xform_dict)


def minimum_two_xforms(value):
    """Validate at least 2 xforms are provided"""
    if len(value) < 2:
        raise serializers.ValidationError(
            _('This field should have at least two unique xforms.'))

    if len(set(value)) != len(value):
        raise serializers.ValidationError(
            _('This field should have unique xforms'))

    return value


def has_matching_fields(value):
    """
    Validate we have some matching fields in the xforms being merged.
    """
    get_merged_xform_survey(value)

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
            dict(i) for i in XFormSerializer(
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
            queryset=XForm.objects.filter(
                is_merged_dataset=False, deleted_at__isnull=True),
            view_name='xform-detail'),
        validators=[minimum_two_xforms, has_matching_fields])
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
            x.last_submission_time.isoformat()
            for x in obj.xforms.only('last_submission_time')
            if x.last_submission_time
        ]
        if values:
            return sorted(values, reverse=True)[0]

    def create(self, validated_data):
        request = self.context['request']
        xforms = validated_data['xforms']
        # create merged xml, json with non conflicting id_string
        survey = get_merged_xform_survey(xforms)
        survey['id_string'] = base64.b64encode(
            uuid.uuid4().hex[:6].encode('utf-8')).decode('utf-8')
        survey['sms_keyword'] = survey['id_string']
        survey['title'] = validated_data.pop('name')
        validated_data['json'] = survey.to_json()
        try:
            validated_data['xml'] = survey.to_xml()
        except PyXFormError as error:
            raise serializers.ValidationError({
                'xforms':
                _("Problem Merging the Form: {}".format(error))
            })
        validated_data['user'] = validated_data['project'].user
        validated_data['created_by'] = request.user
        validated_data['is_merged_dataset'] = True
        validated_data['num_of_submissions'] = sum(
            [__.num_of_submissions for __ in validated_data.get('xforms')])
        validated_data['instances_with_geopoints'] = any([
            __.instances_with_geopoints for __ in validated_data.get('xforms')
        ])

        with transaction.atomic():
            instance = super(MergedXFormSerializer,
                             self).create(validated_data)

            if instance.xforms.all().count() == 0 and xforms:
                for xform in xforms:
                    instance.xforms.add(xform)
                instance.save()

        return instance
