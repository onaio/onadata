from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from rest_framework import serializers
from rest_framework.reverse import reverse
from rest_framework import exceptions

from onadata.apps.logger.models.instance import Instance, InstanceHistory
from onadata.apps.logger.models.xform import XForm
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.logger_tools import safe_create_instance
from onadata.apps.main.models.user_profile import UserProfile


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

        return ret['json'] if 'json' in ret else ret


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
    def create(self, validated_data):
        request = self.context['request']
        view = self.context['view']
        username = view.kwargs.get('username')

        if not username:
            # get the username from the user if not set
            username = (request.user and request.user.username)

        xml_file_list = request.FILES.pop('xml_submission_file', [])
        xml_file = xml_file_list[0] if len(xml_file_list) else None
        media_files = request.FILES.values()

        error, instance = safe_create_instance(
            username, xml_file, media_files, None, request)
        if error:
            raise error  # pylint: disable-msg=E0702

        return instance

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
