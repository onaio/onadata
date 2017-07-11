import base64
import uuid

from django.utils.translation import ugettext as _
from pyxform.builder import create_survey_element_from_json
from rest_framework import serializers

from onadata.apps.logger.models import MergedXForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH


class MergedXFormSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='merged-xform-detail', lookup_field='pk')
    name = serializers.CharField(
        max_length=XFORM_TITLE_LENGTH, write_only=True)

    class Meta:
        model = MergedXForm
        fields = ('url', 'id', 'xforms', 'name', 'project', 'title')

    def validate_xforms(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(
                _('This field should have at least two unique xforms.'))

        if len(set(value)) != len(value):
            raise serializers.ValidationError(
                _('This field should have unique xforms'))

        return value

    def create(self, validated_data):
        # we get the xml and json from the first xforms
        xform = validated_data['xforms'][0]

        # create merged xml, json with non conflicting id_string
        survey = create_survey_element_from_json(xform.json)
        survey['id_string'] = base64.b64encode(uuid.uuid4().hex[:6])
        survey['title'] = validated_data.pop('name')
        validated_data['json'] = survey.to_json()
        validated_data['xml'] = survey.to_xml()

        return super(MergedXFormSerializer, self).create(validated_data)
