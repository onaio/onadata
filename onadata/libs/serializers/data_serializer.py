import json

from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.apps.logger.views import _parse_int


class DataSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='data-list', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'title', 'description', 'url')
        lookup_field = 'pk'


class DataListSerializer(serializers.Serializer):

    @property
    def data(self):
        if self._data is None:
            obj = self.object

            if self.many:
                self._data = []
                for item in obj:
                    self._data.extend(self.to_native(item))
            else:
                self._data = self.to_native(obj)

        return self._data

    def to_native(self, obj):
        request = self.context.get('request')

        if obj is None:
            return super(DataListSerializer, self).to_native(obj)

        query_params = (request and request.QUERY_PARAMS) or {}
        query = {
            ParsedInstance.USERFORM_ID:
            u'%s_%s' % (obj.user.username, obj.id_string)
        }

        try:
            query.update(json.loads(query_params.get('query', '{}')))
        except ValueError:
            raise ParseError(_("Invalid query: %(query)s"
                               % {'query': query_params.get('query')}))

        query_kwargs = {
            'query': json.dumps(query),
            'fields': query_params.get('fields'),
            'sort': query_params.get('sort')
        }

        if request:
            start = request.QUERY_PARAMS.get('start')
            limit = request.QUERY_PARAMS.get('limit')

            start = _parse_int(start)
            if start:
                query_kwargs.update({'start': start})

            limit = _parse_int(limit)
            if limit:
                query_kwargs.update({'limit': limit})

        cursor = ParsedInstance.query_mongo_minimal(**query_kwargs)
        records = list(record for record in cursor)

        return records


class DataInstanceSerializer(serializers.Serializer):

    def to_native(self, obj):
        if obj is None:
            return super(DataInstanceSerializer, self).to_native(obj)

        request = self.context.get('request')
        query_params = (request and request.QUERY_PARAMS) or {}
        query = {
            ParsedInstance.USERFORM_ID:
            u'%s_%s' % (obj.xform.user.username, obj.xform.id_string),
            u'_id': obj.pk
        }
        query_kwargs = {
            'query': json.dumps(query),
            'fields': query_params.get('fields'),
            'sort': query_params.get('sort')
        }
        cursor = ParsedInstance.query_mongo_minimal(**query_kwargs)
        records = list(record for record in cursor)

        return (len(records) and records[0]) or records


class SubmissionSerializer(serializers.Serializer):

    def to_native(self, obj):
        if obj is None:
            return super(SubmissionSerializer, self).to_native(obj)

        return {
            'message': _("Successful submission."),
            'formid': obj.xform.id_string,
            'encrypted': obj.xform.encrypted,
            'instanceID': u'uuid:%s' % obj.uuid,
            'submissionDate': obj.date_created.isoformat(),
            'markedAsCompleteDate': obj.date_modified.isoformat()
        }


class OSMSerializer(serializers.Serializer):
    def to_native(self, obj):
        if obj is None:
            return super(OSMSerializer, self).to_native(obj)

        attachments = Attachment.objects.filter(extension=Attachment.OSM)
        if isinstance(obj, Instance):
            attachments = attachments.filter(instance=obj)
        elif isinstance(obj, XForm):
            attachments = attachments.filter(instance__xform=obj)

        return [a.media_file for a in attachments]
