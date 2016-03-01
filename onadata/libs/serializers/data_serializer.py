from django.utils.translation import ugettext as _

from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models.instance import Instance, InstanceHistory
from onadata.apps.logger.models.xform import XForm
from onadata.libs.serializers.fields.json_field import JsonField


class DataSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='data-list', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'title', 'description', 'url')


class JsonDataSerializer(serializers.Serializer):
    def to_representation(self, obj):
        return obj


class InstanceHistorySerializer(serializers.ModelSerializer):
    json = JsonField()

    class Meta:
        model = InstanceHistory
        fields = ('json', )

    def to_representation(self, instance):
        ret = super(
            InstanceHistorySerializer, self).to_representation(instance)
        if 'json' in ret:
            ret = ret['json']

        return ret


class DataInstanceSerializer(serializers.ModelSerializer):
    json = JsonField()

    class Meta:
        model = Instance
        fields = ('json', )

    def to_representation(self, instance):
        ret = super(DataInstanceSerializer, self).to_representation(instance)
        if 'json' in ret:
            ret = ret['json']

        return ret


class SubmissionSerializer(serializers.Serializer):

    def to_representation(self, obj):
        if obj is None:
            return super(SubmissionSerializer, self).to_representation(obj)

        return {
            'message': _("Successful submission."),
            'formid': obj.xform.id_string,
            'encrypted': obj.xform.encrypted,
            'instanceID': u'uuid:%s' % obj.uuid,
            'submissionDate': obj.date_created.isoformat(),
            'markedAsCompleteDate': obj.date_modified.isoformat()
        }


class OSMSerializer(serializers.Serializer):

    def to_representation(self, obj):
        """
        Return a list of osm file objects from attachments.
        """
        return obj

    @property
    def data(self):
        """
        Returns the serialized data on the serializer.
        """
        if not hasattr(self, '_data'):
            if self.instance is not None and \
                    not getattr(self, '_errors', None):
                self._data = self.to_representation(self.instance)
            elif hasattr(self, '_validated_data') and \
                    not getattr(self, '_errors', None):
                self._data = self.to_representation(self.validated_data)
            else:
                self._data = self.get_initial()

        return self._data


class OSMSiteMapSerializer(serializers.Serializer):
    def to_representation(self, obj):
        """
        Return a list of osm file objects from attachments.
        """
        if obj is None:
            return super(OSMSiteMapSerializer, self).to_representation(obj)

        id_string = obj.get('instance__xform__id_string')
        pk = obj.get('instance__xform')
        title = obj.get('instance__xform__title')
        user = obj.get('instance__xform__user__username')

        kwargs = {'pk': pk}
        url = reverse('osm-list', kwargs=kwargs,
                      request=self.context.get('request'))

        return {
            'url': url, 'title': title, 'id_string': id_string, 'user': user
        }
