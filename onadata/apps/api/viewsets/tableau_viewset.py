import re
from typing import Dict

from rest_framework import status
from collections import defaultdict
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.data import parse_int
from onadata.libs.renderers.renderers import pairing
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.libs.serializers.data_serializer import TableauDataSerializer
from onadata.libs.utils.common_tags import (
    ID, MULTIPLE_SELECT_TYPE, REPEAT_SELECT_TYPE)


def unpack_data_per_qstn_type(key: str, value: str, qstn_type: str) -> Dict:
    data = defaultdict(dict)
    if qstn_type == MULTIPLE_SELECT_TYPE:
        choices = value.split(" ")
        for choice in choices:
            xpaths = f'{key}/{choice}'
            data[xpaths] = choice
    # Allow gps/ geopoint qstn type
    # for backward compatibility
    elif qstn_type == 'geopoint':
        parts = value.split(' ')
        gps_xpaths = \
            DataDictionary.get_additional_geopoint_xpaths(
                key)
        gps_parts = dict(
            [(xpath, None) for xpath in gps_xpaths])
        if len(parts) == 4:
            gps_parts = dict(zip(gps_xpaths, parts))
            data.update(gps_parts)
    else:
        data[key] = value
    return data


def unpack_repeat_data(
        data: list, xform, key: str = None, parent: str = None,
        parent_id: int = None) -> Dict:
    ret = defaultdict(list)
    repeat_dict_key = None

    for idx, repeat in enumerate(data, start=1):
        repeat_data = {}
        repeat_id = None
        if parent_id:
            repeat_id = int(pairing(parent_id, idx))
            repeat_data['_id'] = repeat_id
        for k, v in repeat.items():
            qstn_type = xform.get_element(k).type
            k = k.split('/')
            if qstn_type == REPEAT_SELECT_TYPE:
                nested_repeat_key = ''.join(k[-1])
                parent_key = key or ''.join(k[:1])
                data = unpack_repeat_data(
                    v, xform, key=nested_repeat_key, parent=parent_key,
                    parent_id=repeat_id)

                for k, v in data.items():
                    if isinstance(v, list):
                        value = ret.get(k) or []
                        value.extend(v)
                        ret.update({k: value})
                    else:
                        ret.update({k: v})
            else:
                repeat_dict_key = key or ''.join(k[:1])
                k = ''.join(k[-1])
                repeat_data.update(unpack_data_per_qstn_type(k, v, qstn_type))
                if parent and not repeat_data.get('__parent_table'):
                    repeat_data.update({'__parent_table': parent})
                if parent_id and not repeat_data.get('__parent_id'):
                    repeat_data.update({'__parent_id': parent_id})
        if not isinstance(ret.get(repeat_dict_key), list):
            ret[repeat_dict_key] = []
        ret[repeat_dict_key].append(repeat_data)
    return ret


def process_tableau_data(data, xform):
    result = []
    if data:
        for row in data:
            flat_dict = defaultdict(dict)
            for (key, value) in row.items():
                try:
                    qstn_type = xform.get_element(key).type
                except AttributeError:
                    flat_dict[key] = value
                else:
                    if qstn_type == REPEAT_SELECT_TYPE:
                        flat_dict.update(unpack_repeat_data(
                            value, xform, parent='data',
                            parent_id=row.get(ID)))
                    else:
                        flat_dict.update(unpack_data_per_qstn_type(
                            key, value, qstn_type=qstn_type))
            result.append(dict(flat_dict))
    return result


class TableauViewSet(OpenDataViewSet):
    @action(methods=['GET'], detail=True)
    def data(self, request, **kwargs):
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

            # Filter out deleted submissions
            instances = Instance.objects.filter(
                **qs_kwargs, deleted_at__isnull=True).order_by('pk')

            if count:
                return Response({'count': instances.count()})

            if should_paginate:
                instances = self.paginate_queryset(instances)

            data = process_tableau_data(
                TableauDataSerializer(instances, many=True).data, xform)

            return self.get_streaming_response(data)

        return Response(data)

    @action(methods=['GET'], detail=True)
    def schema(self, request, **kwargs):
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            headers = xform.get_headers(repeat_iterations=1)
            schemas = defaultdict(dict)

            repeat_parent_fields = ['__parent_id', '__parent_table']
            for child in headers:
                # Use regex to identify number of repeats
                repeat_count = len(re.findall(r"\[+\d+\]", child))
                if re.search(r"\[+\d+\]", child):
                    table_name = child.split('/')[repeat_count - 1]
                    table_name = table_name.replace('[1]', '')
                    if not schemas[table_name].get('headers'):
                        schemas[table_name]['headers'] = []
                        schemas[table_name]['headers'].extend(
                            repeat_parent_fields)
                    schemas[table_name]['headers'].append(child.split(
                        '/')[repeat_count])
                    if not schemas[table_name].get('connection_name'):
                        schemas[table_name]['connection_name'] = (
                            f"{xform.project_id}_"
                            f"{xform.id_string}_{table_name}")
                    if not schemas[table_name].get('table_alias'):
                        schemas[table_name]['table_alias'] = table_name
                else:
                    if not schemas['data'].get('headers'):
                        schemas['data']['headers'] = []
                    if not schemas['data'].get('connection_name'):
                        schemas['data']['connection_name'] =\
                            f"{xform.project_id}_{xform.id_string}"
                    if not schemas['data'].get('table_alias'):
                        schemas['data']['table_alias'] = "data"

                    # No need to split the repeats down
                    schemas['data']['headers'].append(child)
            response_data = [
                v for k, v in schemas.items()]
            return Response(data=response_data, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_404_NOT_FOUND)
