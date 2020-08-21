# -*- coding: utf-8 -*-
"""
FloipViewSet: API endpoint for /api/floip
"""
from uuid import UUID
from collections import OrderedDict
import dateutil.parser

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_json_api.pagination import JsonApiPageNumberPagination
from rest_framework_json_api.parsers import JSONParser
from rest_framework_json_api.renderers import JSONRenderer

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import XForm, Instance
from onadata.libs import filters
from onadata.libs.renderers.renderers import (
    convert_instances_to_floip_list, floip_list, inverse_pairing)
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


class FLOIPResponsePageNumberPagination(JsonApiPageNumberPagination):

    def get_paginated_response(self, data, descriptor_id: str):
        next_page_number = None
        previous_page_number = None

        if self.page.has_next():
            next_page_number = self.page.next_page_number()
        if self.page.has_previous():
            previous_page_number = self.page.previous_page_number()

        data_relationships: dict = data.get('relationships', {})
        descriptor_url = self.request.build_absolute_uri(
            reverse('flow-results-detail', kwargs={'uuid': descriptor_id}))
        data_relationships.update(
            {
                "descriptor": {
                    "links": {
                        "self": descriptor_url
                    }
                },
                "links": OrderedDict([
                    ('self', self.build_link(self.page.number)),
                    ('next', self.build_link(next_page_number)),
                    ('previous', self.build_link(previous_page_number))
                ]),
            }
        )
        data["relationships"] = data_relationships
        return Response(data)


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

    pagination_class = FLOIPResponsePageNumberPagination
    parser_classes = (JSONParser, )
    renderer_classes = (FlowResultsJSONRenderer, )

    lookup_field = 'uuid'
    filter_map = {
        "filter[max-version]": "version__lte",
        "filter[min-version]": "version__gte",
        "filter[start-timestamp]": "date_created__gt",
        "filter[end-timestamp]": "date_created__lte",
        "page[afterCursor]": "id__gte",
        "page[beforeCursor]": "id__lte",
    }

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        uuid = self.kwargs.get(self.lookup_field)
        uuid = UUID(uuid, version=4)
        obj = get_object_or_404(queryset, Q(uuid=uuid.hex) | Q(uuid=str(uuid)))
        self.check_object_permissions(self.request, obj)

        if self.request.user.is_anonymous and obj.require_auth:
            self.permission_denied(self.request)
        return obj

    def filter_queryset(self, queryset):
        if self.action == 'responses' and queryset.model == Instance:
            for fil_key, fil_value in self.request.query_params.items():
                if fil_key in self.filter_map:
                    if fil_key in [
                            "filter[max-version]", "filter[min-version]"]:
                        fil_value = dateutil.parser.parse(fil_value)
                        fil_value = fil_value.strftime("%Y%m%d%H%M")

                    if fil_key in ["page[afterCursor]", "page[beforeCursor]"]:
                        fil_value, _ = inverse_pairing(int(fil_value))
                        fil_value = int(fil_value)

                    kwargs = {
                        self.filter_map[fil_key]: fil_value
                    }
                    queryset = queryset.filter(**kwargs)
            return queryset
        return super().filter_queryset(queryset)

    def get_serializer_class(self):
        if self.action == 'list':
            return FloipListSerializer

        if self.action == 'responses':
            return FlowResultsResponseSerializer

        return super(FloipViewSet, self).get_serializer_class()

    def get_success_headers(self, data):
        headers = super(FloipViewSet, self).get_success_headers(data)
        headers['Content-Type'] = 'application/vnd.api+json'
        uuid = str(UUID(data['id']))
        headers['Location'] = self.request.build_absolute_uri(
            reverse('flow-results-detail', kwargs={'uuid': uuid}))

        return headers

    def get_paginated_response(self, data, descriptor_id: str):
        return self.paginator.get_paginated_response(
            data, descriptor_id=descriptor_id)

    @action(methods=['GET', 'POST'], detail=True)
    def responses(self, request, uuid=None):
        """
        Flow Results Responses endpoint.
        """
        status_code = status.HTTP_200_OK
        xform = self.get_object()
        uuid = str(UUID(uuid or xform.uuid, version=4))
        data = {
            "id": uuid,
            "type": "flow-results-data",
            "attributes": {}
        }
        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Location': self.request.build_absolute_uri(
                reverse('flow-results-responses', kwargs={'uuid': uuid}))
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
            if xform.is_merged_dataset:
                pks = xform.mergedxform.xforms.filter(
                    deleted_at__isnull=True
                ).values_list('pk', flat=True)
                queryset = Instance.objects.filter(
                    xform_id__in=pks,
                    deleted_at__isnull=True).values_list('json', flat=True)
            else:
                queryset = xform.instances.values_list('json', flat=True)

            queryset = self.filter_queryset(queryset)
            afterCursor = None
            beforeCursor = None
            if 'page[afterCursor]' in self.request.query_params:
                afterCursor = int(
                    self.request.query_params['page[afterCursor]'])

            if 'page[beforeCursor]' in self.request.query_params:
                beforeCursor = int(
                    self.request.query_params['page[beforeCursor]']
                )

            if "page[size]" in self.request.query_params:
                responses = convert_instances_to_floip_list(
                    queryset,
                    afterCursor=afterCursor, beforeCursor=beforeCursor)
                data['attributes']['responses'] = self.paginate_queryset(
                    responses)
                response = self.get_paginated_response(
                    data, descriptor_id=uuid)
                for key, value in headers.items():
                    response[key] = value
                return response

            data['attributes']['responses'] = floip_list(
                queryset, afterCursor=afterCursor, beforeCursor=beforeCursor)
        return Response(data, headers=headers, status=status_code)
