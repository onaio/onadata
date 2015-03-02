from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm


class DataSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='data-list', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'title', 'description', 'url')
        lookup_field = 'pk'


class JsonDataSerializer(serializers.Serializer):
    def to_native(self, obj):
        return obj


class DataListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instance

    def to_native(self, obj):
        data = {}
        if obj:
            if obj.json.get('_id') is None:
                data = obj.get_full_dict()
            else:
                data = obj.json

        return data


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
        """
        Return a list of osm file objects from attachments.
        """
        if obj is None:
            return super(OSMSerializer, self).to_native(obj)

        attachments = Attachment.objects.filter(extension=Attachment.OSM)
        if isinstance(obj, Instance):
            attachments = attachments.filter(instance=obj)
        elif isinstance(obj, XForm):
            attachments = attachments.filter(instance__xform=obj)

        return [a.media_file for a in attachments]

    @property
    def data(self):
        """
        Returns the serialized data on the serializer.
        """
        if self._data is None:
            obj = self.object

            if self.many:
                self._data = []
                for item in obj:
                    self._data.extend(self.to_native(item))
            else:
                self._data = self.to_native(obj)

        return self._data


class OSMSiteMapSerializer(serializers.Serializer):
    def to_native(self, obj):
        """
        Return a list of osm file objects from attachments.
        """
        if obj is None:
            return super(OSMSiteMapSerializer, self).to_native(obj)

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
