# -*- coding=utf-8 -*-
"""
Submission data serializers module.
"""
from io import BytesIO

from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from rest_framework import exceptions, serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models.instance import Instance, InstanceHistory
from onadata.apps.logger.models.xform import XForm
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.dict_tools import (dict_lists2strings, dict_paths2dict,
                                           query_list_to_dict,
                                           floip_response_headers_dict)
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance


NUM_FLOIP_COLUMNS = 6


def get_request_and_username(context):
    """
    Returns request object and username
    """
    request = context['request']
    view = context['view']
    username = view.kwargs.get('username')

    if not username:
        # get the username from the user if not set
        username = (request.user and request.user.username)

    return (request, username)


def create_submission(request, username, data_dict, xform_id):
    """
    Returns validated data object instances
    """
    xml_string = dict2xform(data_dict, xform_id)
    xml_file = BytesIO(xml_string.encode('utf-8'))

    error, instance = safe_create_instance(username, xml_file, [], None,
                                           request)
    if error:
        raise serializers.ValidationError(error.message)

    return instance


class DataSerializer(serializers.HyperlinkedModelSerializer):
    """
    DataSerializer class - used for the list view to show `id`, `id_string`,
    `title` and `description`.
    """
    url = serializers.HyperlinkedIdentityField(
        view_name='data-list', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'title', 'description', 'url')


class JsonDataSerializer(serializers.Serializer):  # pylint: disable=W0223
    """
    JSON DataSerializer class - for json field data representation.
    """

    def to_representation(self, instance):
        return instance


class InstanceHistorySerializer(serializers.ModelSerializer):
    """
    InstanceHistorySerializer class - for the json field data representation.
    """
    json = JsonField()

    class Meta:
        model = InstanceHistory
        fields = ('json', )

    def to_representation(self, instance):
        ret = super(InstanceHistorySerializer,
                    self).to_representation(instance)

        return ret['json'] if 'json' in ret else ret


class DataInstanceSerializer(serializers.ModelSerializer):
    """
    DataInstanceSerializer class - for json field data representation on the
    Instance (submission) model.
    """
    json = JsonField()

    class Meta:
        model = Instance
        fields = ('json', )

    def to_representation(self, instance):
        ret = super(DataInstanceSerializer, self).to_representation(instance)
        if 'json' in ret:
            ret = ret['json']

        return ret


class SubmissionSuccessMixin(object):  # pylint: disable=R0903
    """
    SubmissionSuccessMixin - prepares submission success data/message.
    """

    def to_representation(self, instance):
        """
        Returns a dict with a successful submission message.
        """
        if instance is None:
            return super(SubmissionSuccessMixin, self)\
                .to_representation(instance)

        return {
            'message': _("Successful submission."),
            'formid': instance.xform.id_string,
            'encrypted': instance.xform.encrypted,
            'instanceID': u'uuid:%s' % instance.uuid,
            'submissionDate': instance.date_created.isoformat(),
            'markedAsCompleteDate': instance.date_modified.isoformat()
        }


# pylint: disable=W0223
class SubmissionSerializer(SubmissionSuccessMixin, serializers.Serializer):
    """
    XML SubmissionSerializer - handles creating a submission from XML.
    """

    def validate(self, attrs):
        request, __ = get_request_and_username(self.context)
        if not request.FILES or 'xml_submission_file' not in request.FILES:
            raise serializers.ValidationError(_("No XML submission file."))

        return super(SubmissionSerializer, self).validate(attrs)

    def create(self, validated_data):
        """
        Returns object instances based on the validated data
        """
        request, username = get_request_and_username(self.context)

        xml_file_list = request.FILES.pop('xml_submission_file', [])
        xml_file = xml_file_list[0] if xml_file_list else None
        media_files = request.FILES.values()

        error, instance = safe_create_instance(username, xml_file, media_files,
                                               None, request)
        if error:
            exc = exceptions.APIException(detail=error)
            exc.response = error
            exc.status_code = error.status_code

            raise exc

        return instance


class OSMSerializer(serializers.Serializer):
    """
    OSM Serializer - represents OSM data.
    """

    def to_representation(self, instance):
        """
        Return a list of osm file objects from attachments.
        """
        return instance

    # pylint: disable=W0201
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
    """
    OSM SiteMap Serializer.
    """

    def to_representation(self, instance):
        """
        Return a list of osm file objects from attachments.
        """
        if instance is None:
            return super(OSMSiteMapSerializer, self)\
                .to_representation(instance)

        id_string = instance.get('instance__xform__id_string')
        title = instance.get('instance__xform__title')
        user = instance.get('instance__xform__user__username')

        kwargs = {'pk': instance.get('instance__xform')}
        url = reverse(
            'osm-list', kwargs=kwargs, request=self.context.get('request'))

        return {
            'url': url,
            'title': title,
            'id_string': id_string,
            'user': user
        }


class JSONSubmissionSerializer(SubmissionSuccessMixin, serializers.Serializer):
    """
    JSON SubmissionSerializer - handles JSON submission data.
    """

    def validate(self, attrs):
        """
        Custom submission validator in request data.
        """
        request = self.context['request']

        if 'submission' not in request.data:
            raise serializers.ValidationError({
                'submission':
                _(u"No submission key provided.")
            })

        submission = request.data.get('submission')
        if not submission:
            raise serializers.ValidationError({
                'submission':
                _(u"Received empty submission. No instance was created")
            })

        return super(JSONSubmissionSerializer, self).validate(attrs)

    def create(self, validated_data):
        """
        Returns object instances based on the validated data
        """
        request, username = get_request_and_username(self.context)
        submission = request.data.get('submission')
        # convert lists in submission dict to joined strings
        try:
            submission_joined = dict_paths2dict(dict_lists2strings(submission))
        except AttributeError:
            raise serializers.ValidationError(
                _(u'Incorrect format, see format details here,'
                  u'https://api.ona.io/static/docs/submissions.html.'))

        instance = create_submission(request, username, submission_joined,
                                     request.data.get('id'))

        return instance


class RapidProSubmissionSerializer(SubmissionSuccessMixin,
                                   serializers.Serializer):
    """
    Rapidpro SubmissionSerializer - handles Rapidpro webhook post.
    """
    def validate(self, attrs):
        """
        Custom xform id validator in views kwargs.
        """
        view = self.context['view']

        if 'xform_pk' in view.kwargs:
            xform_pk = view.kwargs.get('xform_pk')
            xform = get_object_or_404(XForm, pk=xform_pk)
            attrs.update({'id_string': xform.id_string})
        else:
            raise serializers.ValidationError({
                'xform_pk':
                _(u'Incorrect url format, Use format '
                  u'https://api.ona.io/username/formid/submission')
            })

        return super(RapidProSubmissionSerializer, self).validate(attrs)

    def create(self, validated_data):
        """
        Returns object instances based on the validated data.
        """
        request, username = get_request_and_username(self.context)
        rapidpro_dict = query_list_to_dict(request.data.get('values'))
        instance = create_submission(request, username, rapidpro_dict,
                                     validated_data['id_string'])

        return instance


class FLOIPListSerializer(serializers.ListSerializer):
    """
    Custom ListSerializer for a FLOIP submission.
    """
    def create(self, validated_data):
        """
        Returns object instances based on the validated data.
        """
        request, username = get_request_and_username(self.context)
        xform_pk = self.context['view'].kwargs['xform_pk']
        xform = get_object_or_404(XForm, pk=xform_pk)
        xform_headers = xform.get_keys()
        flow_dict = floip_response_headers_dict(request.data, xform_headers)
        instance = create_submission(request, username, flow_dict,
                                     xform)
        return [instance]


class FLOIPSubmissionSerializer(SubmissionSuccessMixin,
                                serializers.Serializer):
    """
    FLOIP SubmmissionSerializer - Handles a row of FLOIP specification format.
    """
    def run_validators(self, value):
        # Only run default run_validators if we have validators attached to the
        # serializer.
        if self.validators:
            return super(FLOIPSubmissionSerializer, self).run_validators(value)

        return []

    def validate(self, attrs):
        """
        Custom list data validator.
        """
        data = self.context['request'].data
        error_msg = None

        if not isinstance(data, list):
            error_msg = u'Invalid format. Expecting a list.'
        elif data:
            for row_i, row in enumerate(data):
                if len(row) != NUM_FLOIP_COLUMNS:
                    error_msg = _(u"Wrong number of values (%(values)d) in row"
                                  " %(row)d, expecting %(expected)d values"
                                  % {'row': row_i,
                                     'values': (len(row)),
                                     'expected': NUM_FLOIP_COLUMNS})
                break

        if error_msg:
            raise serializers.ValidationError(_(error_msg))

        return super(FLOIPSubmissionSerializer, self).validate(attrs)

    def to_internal_value(self, data):
        """
        Overrides validating rows in list data.
        """
        if isinstance(data, list) and len(data) == 6:
            data = {data[1]: data}

        return data

    class Meta:
        """
        Call the list serializer class to create an instance.
        """
        list_serializer_class = FLOIPListSerializer
