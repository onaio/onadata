import json
import re

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from rest_framework import status
from rest_framework.decorators import detail_route, list_route
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import OpenDataViewSetPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.models.open_data import OpenData
from onadata.libs.data import parse_int
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.total_header_mixin import TotalHeaderMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.data_serializer import DataInstanceSerializer
from onadata.libs.serializers.open_data_serializer import OpenDataSerializer
from onadata.libs.utils.csv_builder import CSVDataFrameBuilder

BaseViewset = get_baseviewset_class()
IGNORED_FIELD_TYPES = ['select one', 'select multiple']


def replace_special_characters_with_underscores(data):
    return [re.sub(r"\W", r"_", a) for a in data]


class OpenDataViewSet(ETagsMixin, CacheControlMixin, TotalHeaderMixin,
                      BaseViewset, ModelViewSet):
    permission_classes = (OpenDataViewSetPermissions, )
    queryset = OpenData.objects.filter()
    lookup_field = 'uuid'
    serializer_class = OpenDataSerializer
    flattened_dict = {}
    MAX_INSTANCES_PER_REQUEST = 1000
    pagination_class = StandardPageNumberPagination

    def get_tableau_type(self, xform_type):
        '''
        Returns a tableau-supported type based on a xform type.
        '''
        tableau_types = {
            'integer': 'int',
            'decimal': 'float',
            'dateTime': 'datetime',
            'text': 'string'
        }

        return tableau_types.get(xform_type, 'string')

    def flatten_xform_columns(self, json_of_columns_fields):
        '''
        Flattens a json of column fields and the result is set to a class
        variable.
        '''
        for a in json_of_columns_fields:
            self.flattened_dict[a.get('name')] = self.get_tableau_type(
                a.get('type'))
            # using IGNORED_FIELD_TYPES so that choice values are not included.
            if a.get('children') and a.get('type') not in IGNORED_FIELD_TYPES:
                self.flatten_xform_columns(a.get('children'))

    def get_tableau_column_headers(self):
        '''
        Retrieve columns headers that are valid in tableau.
        '''
        tableau_colulmn_headers = []

        def append_to_tableau_colulmn_headers(header, question_type=None):
            quest_type = 'string'
            if question_type:
                quest_type = question_type

            # alias can be updated in the future to question labels
            tableau_colulmn_headers.append({
                'id': header,
                'dataType': quest_type,
                'alias': header
            })

        # using nested loops to determine what valid data types to set for
        # tableau.
        for header in self.xform_headers:
            for quest_name, quest_type in self.flattened_dict.items():
                if header == quest_name or header.endswith('_%s' % quest_name):
                    append_to_tableau_colulmn_headers(header, quest_type)
                    break
            else:
                if header == '_id':
                    append_to_tableau_colulmn_headers(header, "int")
                else:
                    append_to_tableau_colulmn_headers(header)

        return tableau_colulmn_headers

    @detail_route(methods=['GET'])
    def data(self, request, **kwargs):
        """
        Streams submission data response matching uuid in the request.
        """
        self.object = self.get_object()
        # get greater than value and cast it to an int
        gt_id = request.query_params.get('gt_id')
        gt_id = gt_id and parse_int(gt_id)
        count = request.query_params.get('count')
        pagination_keys = [
            self.paginator.page_query_param,
            self.paginator.page_size_query_param
        ]
        query_param_keys = request.query_params
        should_paginate = any([k in query_param_keys for k in pagination_keys])

        data = []
        if isinstance(self.object.content_object, XForm):
            if not self.object.active:
                return Response(status=status.HTTP_404_NOT_FOUND)

            xform = self.object.content_object
            if xform.is_merged_dataset:
                qs_kwargs = {'xform_id__in': list(
                    xform.mergedxform.xforms.values_list('pk', flat=True))}
            else:
                qs_kwargs = {'xform_id': xform.pk}
            if gt_id:
                qs_kwargs.update({'id__gt': gt_id})

            instances = Instance.objects.filter(**qs_kwargs).order_by('pk')
            length = self.total_count = instances.count()

            if count:
                return Response({'count': self.total_count})

            if should_paginate:
                instances = self.paginate_queryset(instances)
                length = 1 + self.paginator.page.end_index(
                ) - self.paginator.page.start_index()

            csv_df_builder = CSVDataFrameBuilder(
                xform.user.username, xform.id_string, include_images=False)
            data = csv_df_builder._format_for_dataframe(
                DataInstanceSerializer(instances, many=True).data)

            return self._get_streaming_response(data, length)

        return Response(data)

    def _get_streaming_response(self, data, length):
        """Get a StreamingHttpResponse response object"""

        def stream_json(streaming_data, length):
            """Generator function to stream JSON data"""
            yield u"["

            for i, d in enumerate(streaming_data, start=1):
                yield json.dumps({
                    re.sub(r"\W", r"_", a): b for a, b in d.items()
                })
                yield "" if i == length else ","

            yield u"]"

        response = StreamingHttpResponse(
            stream_json(data, length), content_type="application/json")

        # set headers on streaming response
        for k, v in self.headers.items():
            response[k] = v

        return response

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(methods=['GET'])
    def schema(self, request, **kwargs):
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            headers = xform.get_headers()
            self.xform_headers = replace_special_characters_with_underscores(
                headers)

            xform_json = json.loads(xform.json)
            self.flatten_xform_columns(
                json_of_columns_fields=xform_json.get('children'))

            tableau_column_headers = self.get_tableau_column_headers()

            data = {
                'column_headers': tableau_column_headers,
                'connection_name': "%s_%s" % (xform.project_id,
                                              xform.id_string),
                'table_alias': xform.title
            }

            return Response(data=data, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_404_NOT_FOUND)

    @list_route(methods=['GET'])
    def uuid(self, request, *args, **kwargs):
        data_type = request.query_params.get('data_type')
        object_id = request.query_params.get('object_id')

        if not data_type or not object_id:
            return Response(
                data="Query params data_type and object_id are required",
                status=status.HTTP_400_BAD_REQUEST)

        if data_type == 'xform':
            xform = get_object_or_404(XForm, id=object_id)
            if request.user.has_perm("change_xform", xform):
                ct = ContentType.objects.get_for_model(xform)
                _open_data = get_object_or_404(
                    OpenData, object_id=object_id, content_type=ct)
                if _open_data:
                    return Response(
                        data={'uuid': _open_data.uuid},
                        status=status.HTTP_200_OK)
            else:
                raise PermissionDenied(
                    _((u"You do not have permission to perform this action.")))

        return Response(status=status.HTTP_404_NOT_FOUND)
