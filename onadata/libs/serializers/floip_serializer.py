# -*- coding: utf-8 -*-
"""
FloipSerializer module.

"""
import json
import os
from copy import deepcopy
from cStringIO import StringIO

import six
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from floip import survey_to_floip_package
from rest_framework.reverse import reverse
from rest_framework_json_api import serializers

from onadata.apps.api.tools import do_publish_xlsform
from onadata.apps.logger.models import XForm
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance


def _get_user(username):
    users = User.objects.filter(username__iexact=username)

    return users.first()


def _get_owner(request):
    owner = request.data.get('owner') or request.user

    if isinstance(owner, six.string_types):
        owner_obj = _get_user(owner)

        if owner_obj is None:
            raise ValidationError(
                _(u"User with username %s does not exist." % owner))
        return owner_obj
    return owner


def parse_responses(responses, session_id_index=3, question_index=4,
                    answer_index=5):
    """
    Returns individual submission for all responses in a flow-results responses
    package.
    """
    submission = {}
    current_key = None
    for row in responses:
        if len(row) < 6:
            continue
        if current_key is None:
            current_key = row[session_id_index]
        if current_key != row[session_id_index]:
            yield submission
            submission = {}
            current_key = row[session_id_index]
        submission[row[question_index]] = row[answer_index]

    yield submission


# pylint: disable=too-many-ancestors
class FloipListSerializer(serializers.HyperlinkedModelSerializer):
    """
    FloipListSerializer class.
    """
    url = serializers.HyperlinkedIdentityField(
        view_name='flow-results-detail', lookup_field='uuid')
    name = serializers.ReadOnlyField(source='id_string')
    created = serializers.ReadOnlyField(source='date_created')
    modified = serializers.ReadOnlyField(source='date_modified')

    class JSONAPIMeta:  # pylint: disable=old-style-class,no-init,R0903
        """
        JSON API metaclass.
        """
        resource_name = 'package'

    class Meta:
        model = XForm
        fields = ('url', 'id', 'name', 'title', 'created', 'modified')


class FloipSerializer(serializers.HyperlinkedModelSerializer):
    """
    FloipSerializer class.
    """
    url = serializers.HyperlinkedIdentityField(
        view_name='floip-detail', lookup_field='pk')
    profile = serializers.SerializerMethodField()
    created = serializers.ReadOnlyField(source='date_created')
    modified = serializers.ReadOnlyField(source='date_modified')
    # pylint: disable=invalid-name
    flow_results_specification_version = serializers.SerializerMethodField()
    resources = serializers.SerializerMethodField()

    class JSONAPIMeta:  # pylint: disable=old-style-class,no-init,R0903
        """
        JSON API metaclass.
        """
        resource_name = 'package'

    class Meta:
        model = XForm
        fields = ('url', 'id', 'id_string', 'title', 'profile', 'created',
                  'modified', 'flow_results_specification_version',
                  'resources')

    def get_profile(self, value):  # pylint: disable=no-self-use,W0613
        """
        Returns the data-package profile.
        """
        return 'data-package'

    # pylint: disable=no-self-use,unused-argument
    def get_flow_results_specification_version(self, value):
        """
        Returns the flow results specification version.
        """
        return '1.0.0-rc1'

    def get_resources(self, value):  # pylint: disable=no-self-use,W0613
        """
        Returns empty dict, a dummy holder for the eventually generated data
        package resources.
        """
        return {}

    def create(self, validated_data):
        request = self.context['request']
        data = deepcopy(request.data)
        if 'profile' in data and data['profile'] == 'flow-results-package':
            data['profile'] = 'data-package'
        descriptor = StringIO(json.dumps(data))
        descriptor.seek(0, os.SEEK_END)
        floip_file = InMemoryUploadedFile(
            descriptor,
            'floip_file',
            request.data.get('name') + '.json',
            'application/json',
            descriptor.tell(),
            charset=None)
        files = {'floip_file': floip_file}
        instance = do_publish_xlsform(request.user, None, files, request.user)
        if isinstance(instance, XForm):
            return instance

        raise serializers.ValidationError(instance)

    def to_representation(self, instance):
        request = self.context['request']
        data_url = request.build_absolute_uri(
            reverse('flow-results-responses', kwargs={'uuid': instance.uuid}))
        package = survey_to_floip_package(
            json.loads(instance.json), instance.uuid, instance.date_created,
            instance.date_modified, data_url)

        data = package.descriptor
        if data['profile'] != 'flow-results-package':
            data['profile'] = 'flow-results-package'

        return data


class FlowResultsResponse(object):  # pylint: disable=too-few-public-methods
    """
    FLowResultsResponse class to hold a list of submission ids.
    """
    id = None  # pylint: disable=invalid-name
    responses = []

    def __init__(self, uuid, responses):
        self.id = uuid  # pylint: disable=invalid-name
        self.responses = responses


class FlowResultsResponseSerializer(serializers.Serializer):
    """
    FlowResultsResponseSerializer for handling publishing of Flow Results
    Response package.
    """
    id = serializers.CharField()  # pylint: disable=invalid-name
    responses = serializers.ListField()

    def create(self, validated_data):
        request = self.context['request']
        responses = validated_data['responses']
        xform = get_object_or_404(XForm, uuid=validated_data['id'])
        processed = []
        for submission in parse_responses(responses):
            xml_file = StringIO(
                dict2xform(submission, xform.id_string, 'data'))

            error, instance = safe_create_instance(
                request.user.username, xml_file, [], None, request)
            processed.append(instance.pk)
            if error:
                raise serializers.ValidationError(error)

        return FlowResultsResponse(xform.uuid, responses)

    def update(self, instance, validated_data):
        pass
