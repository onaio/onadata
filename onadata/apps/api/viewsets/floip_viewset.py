# -*- coding: utf-8 -*-
"""
FloipViewSet: API endpoint for /api/floip
"""
from cStringIO import StringIO

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import detail_route
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_json_api.parsers import JSONParser
from rest_framework_json_api.renderers import JSONRenderer

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import XForm
from onadata.libs import filters
from onadata.libs.renderers.renderers import floip_list
from onadata.libs.serializers.floip_serializer import (FloipListSerializer,
                                                       FloipSerializer)
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance


def parse_responses(responses):
    """
    Returns individual submission for all responses in a flow-results responses
    package.
    """
    submission = {}
    current_key = None
    for row in responses:
        if current_key is None:
            current_key = row[1]
        if current_key != row[1]:
            yield submission
            submission = {}
            current_key = row[1]
        submission[row[3]] = row[4]

    yield submission


# pylint: disable=too-many-ancestors
class FloipViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin,
                   mixins.ListModelMixin, mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    """
    FloipViewSet: create, list, retrieve, destroy
    """

    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.PublicDatasetsFilter)
    permission_classes = [XFormPermissions]
    queryset = XForm.objects.filter(deleted_at__isnull=True)
    serializer_class = FloipSerializer

    parser_classes = (JSONParser, )
    renderer_classes = (JSONRenderer, )
    resource_name = ['packages', 'responses']

    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.action == 'list':
            return FloipListSerializer
        return super(FloipViewSet, self).get_serializer_class()

    def get_success_headers(self, data):
        headers = super(FloipViewSet, self).get_success_headers(data)
        headers['Content-Type'] = 'application/vnd.api+json'
        headers['Location'] = self.request.build_absolute_uri(
            reverse('flow-results-detail', kwargs={'uuid': data['id']}))

        return headers

    @detail_route(methods=['get', 'post'])
    def responses(self, request, uuid=None):
        """
        FlOIP results.
        """
        status_code = status.HTTP_200_OK
        xform = self.get_object()
        if request.method == 'POST':
            responses = request.data.get('responses', [])
            for submission in parse_responses(responses):
                xml_string = dict2xform(submission, xform.id_string, 'data')
                xml_file = StringIO(xml_string)

                error, _instance = safe_create_instance(
                    request.user.username, xml_file, [], None, request)
                if error:
                    raise ParseError(error)
            status_code = status.HTTP_201_CREATED
        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Location': self.request.build_absolute_uri(
                reverse('flow-results-responses', kwargs={'uuid': xform.uuid}))
        }  # yapf: disable

        return Response(
            {
                "id": uuid,
                "type": "flow-results-data",
                "responses":
                floip_list(xform.instances.values_list('json', flat=True))
            }, headers=headers, status=status_code)  # yapf: disable
