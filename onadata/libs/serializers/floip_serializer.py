# -*- coding: utf-8 -*-
"""
FloipSerializer module.

"""
import json
import os
from copy import deepcopy
from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _

import six
from floip import survey_to_floip_package
from rest_framework.reverse import reverse
from rest_framework_json_api import serializers

from onadata.apps.api.tools import do_publish_xlsform
from onadata.apps.logger.models import XForm
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance

CONTACT_ID_INDEX = getattr(settings, 'FLOW_RESULTS_CONTACT_ID_INDEX', 2)
SESSION_ID_INDEX = getattr(settings, 'FLOW_RESULTS_SESSION_ID_INDEX', 3)
QUESTION_INDEX = getattr(settings, 'FLOW_RESULTS_QUESTION_INDEX', 4)
ANSWER_INDEX = getattr(settings, 'FLOW_RESULTS_ANSWER_INDEX', 5)


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


def parse_responses(responses, session_id_index=SESSION_ID_INDEX,
                    question_index=QUESTION_INDEX, answer_index=ANSWER_INDEX,
                    contact_id_index=CONTACT_ID_INDEX):
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
        if 'meta' not in submission:
            submission['meta'] = {
                'instanceID': 'uuid:%s' % current_key,
                'sessionID': current_key,
                'contactID': row[contact_id_index]
            }
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
    id = serializers.ReadOnlyField(source='uuid')  # pylint: disable=C0103
    name = serializers.ReadOnlyField(source='id_string')
    created = serializers.ReadOnlyField(source='date_created')
    modified = serializers.ReadOnlyField(source='date_modified')

    class JSONAPIMeta:  # pylint: disable=old-style-class,no-init,R0903
        """
        JSON API metaclass.
        """
        resource_name = 'packages'

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
        resource_name = 'packages'

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

    def _process_request(self, request, update_instance=None):
        data = deepcopy(request.data)
        if 'profile' in data and data['profile'] == 'flow-results-package':
            data['profile'] = 'data-package'
        descriptor = BytesIO(json.dumps(data).encode('utf-8'))
        descriptor.seek(0, os.SEEK_END)
        floip_file = InMemoryUploadedFile(
            descriptor,
            'floip_file',
            request.data.get('name') + '.json',
            'application/json',
            descriptor.tell(),
            charset=None)
        kwargs = {
            'user': request.user,
            'post': None,
            'files': {'floip_file': floip_file},
            'owner': request.user,
        }
        if update_instance:
            kwargs['id_string'] = update_instance.id_string
            kwargs['project'] = update_instance.project
        instance = do_publish_xlsform(**kwargs)
        if isinstance(instance, XForm):
            return instance

        raise serializers.ValidationError(instance)

    def create(self, validated_data):
        request = self.context['request']

        return self._process_request(request)

    def update(self, instance, validated_data):
        request = self.context['request']

        return self._process_request(request, instance)

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
    duplicates = 0

    def __init__(self, session_id, responses, duplicates=None):
        self.id = session_id  # pylint: disable=invalid-name
        self.responses = responses
        self.duplicates = duplicates


class FlowResultsResponseSerializer(serializers.Serializer):
    """
    FlowResultsResponseSerializer for handling publishing of Flow Results
    Response package.
    """
    id = serializers.CharField()  # pylint: disable=invalid-name
    responses = serializers.ListField()
    duplicates = serializers.IntegerField(read_only=True)

    class JSONAPIMeta:  # pylint: disable=old-style-class,no-init,R0903
        """
        JSON API metaclass.
        """
        resource_name = 'responses'

    def create(self, validated_data):
        duplicates = 0
        request = self.context['request']
        responses = validated_data['responses']
        xform = get_object_or_404(XForm, uuid=validated_data['id'],
                                  deleted_at__isnull=True)
        for submission in parse_responses(responses):
            xml_file = BytesIO(dict2xform(
                submission, xform.id_string, 'data').encode('utf-8'))

            error, _instance = safe_create_instance(
                request.user.username, xml_file, [], None, request)
            if error and error.status_code != 202:
                raise serializers.ValidationError(error)
            if error and error.status_code == 202:
                duplicates += 1

        return FlowResultsResponse(xform.uuid, responses, duplicates)

    def update(self, instance, validated_data):
        pass
