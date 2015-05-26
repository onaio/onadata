from django.core.validators import ValidationError
from django.utils.translation import ugettext as _

from rest_framework import serializers

from onadata.libs.serializers.fields.json_field import JsonField
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.data_view import SUPPORTED_FILTERS


class DataViewSerializer(serializers.HyperlinkedModelSerializer):

    name = serializers.CharField(max_length=255, source='name')
    url = serializers.HyperlinkedIdentityField(view_name='dataviews-detail',
                                               lookup_field='pk')
    xform = serializers.HyperlinkedRelatedField(view_name='xform-detail',
                                                source='xform',
                                                lookup_field='pk')
    project = serializers.HyperlinkedRelatedField(view_name='project-detail',
                                                  source='project',
                                                  lookup_field='pk')
    columns = JsonField(source='columns')
    query = JsonField(source='query', required=False)

    class Meta:
        model = DataView

    def validate_query(self, attrs, source):
        query = attrs.get('query')

        if query:
            for q in query:
                if 'column' not in q:
                    raise ValidationError(_(u"`column` not set in query"))

                if 'filter' not in q:
                    raise ValidationError(_(u"`filter` not set in query"))

                if 'value' not in q:
                    raise ValidationError(_(u"`value` not set in query"))

                comp = q.get('filter')

                if comp not in SUPPORTED_FILTERS:
                    raise ValidationError(_(u"Filter not supported"))

        return attrs

    def validate_columns(self, attrs, source):
        columns = attrs.get('columns')

        if not isinstance(columns, list):
            raise ValidationError(_(u"`columns` should be a list of columns"))

        return attrs
