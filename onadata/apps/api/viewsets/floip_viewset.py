# -*- coding: utf-8 -*-
"""
FloipViewSet: API endpoint for /api/floip
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_json_api.pagination import PageNumberPagination
from rest_framework_json_api.parsers import JSONParser
from rest_framework_json_api.renderers import JSONRenderer

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import XForm
from onadata.libs import filters
from onadata.libs.renderers.renderers import floip_list
from onadata.libs.serializers.floip_serializer import (
    FloipListSerializer, FloipSerializer, FlowResultsResponseSerializer)


class FlowResultsJSONRenderer(JSONRenderer):
    """
    Render JSON API format with uuid.
    """

    # pylint: disable=too-many-arguments
    @classmethod
    def build_json_resource_obj(cls, fields, resource, resource_instance,
                                resource_name, force_type_resolution=False):
        """
        Build a JSON resource object using the id as it appears in the
        resource.
        """
        obj = super(FlowResultsJSONRenderer, cls).build_json_resource_obj(
            fields, resource, resource_instance, resource_name,
            force_type_resolution)
        obj['id'] = resource['id']

        return obj


# pylint: disable=too-many-ancestors
class FloipViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin,
                   mixins.ListModelMixin, mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    FloipViewSet: create, list, retrieve, destroy
    """

    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.PublicDatasetsFilter)
    permission_classes = [XFormPermissions]
    queryset = XForm.objects.filter(deleted_at__isnull=True)
    serializer_class = FloipSerializer

    pagination_class = PageNumberPagination
    parser_classes = (JSONParser, )
    renderer_classes = (FlowResultsJSONRenderer, )

    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.action == 'list':
            return FloipListSerializer

        if self.action == 'responses':
            return FlowResultsResponseSerializer

        return super(FloipViewSet, self).get_serializer_class()

    def get_success_headers(self, data):
        headers = super(FloipViewSet, self).get_success_headers(data)
        headers['Content-Type'] = 'application/vnd.api+json'
        headers['Location'] = self.request.build_absolute_uri(
            reverse('flow-results-detail', kwargs={'uuid': data['id']}))

        return headers

    @action(methods=['GET', 'POST'], detail=True)
    def responses(self, request, uuid=None):
        """
        Flow Results Responses endpoint.
        """
        status_code = status.HTTP_200_OK
        xform = self.get_object()
        data = {
            "id": uuid or xform.uuid,
            "type": "flow-results-data",
        }
        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Location': self.request.build_absolute_uri(
                reverse('flow-results-responses', kwargs={'uuid': xform.uuid}))
        }  # yapf: disable
        if request.method == 'POST':
            serializer = FlowResultsResponseSerializer(
                data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            data['response'] = serializer.data['responses']
            if serializer.data['duplicates']:
                status_code = status.HTTP_202_ACCEPTED
            else:
                status_code = status.HTTP_201_CREATED
        else:
            queryset = xform.instances.values_list('json', flat=True)
            paginate_queryset = self.paginate_queryset(queryset)
            if paginate_queryset:
                data['responses'] = floip_list(paginate_queryset)
                response = self.get_paginated_response(data)
                for key, value in headers.items():
                    response[key] = value

                return response

            data['responses'] = floip_list(queryset)

        return Response(data, headers=headers, status=status_code)
