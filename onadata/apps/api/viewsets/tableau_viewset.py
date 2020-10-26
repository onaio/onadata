import json
import re
from typing import Dict, List

from rest_framework import status
from collections import defaultdict
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.data import parse_int
from onadata.libs.renderers.renderers import pairing
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.api.viewsets.open_data_viewset import (
    OpenDataViewSet, IGNORED_FIELD_TYPES, remove_metadata_fields)
from onadata.libs.serializers.data_serializer import TableauDataSerializer
from onadata.libs.utils.common_tags import (
    ID, MULTIPLE_SELECT_TYPE, REPEAT_SELECT_TYPE)


def unpack_data_per_qstn_type(key: str, value: str, qstn_type: str) -> Dict:
    data = defaultdict(dict)
    if qstn_type == MULTIPLE_SELECT_TYPE:
        data[key] = value
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


def clean_xform_headers(headers: list) -> list:
    ret = []
    for header in headers:
        if re.search(r"\[+\d+\]", header):
            repeat_count = len(re.findall(r"\[+\d+\]", header))
            header = header.split('/')[repeat_count].replace('[1]', '')
            if header == 'gps':
                continue

        # Replace special character with underscore
        header = re.sub(r"\W", r"_", header)
        ret.append(header)
    return ret


class TableauViewSet(OpenDataViewSet):
    flattened_dict = defaultdict(list)

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

    # pylint: disable=arguments-differ
    def flatten_xform_columns(
            self, json_of_columns_fields, table: str = None):
        '''
        Flattens a json of column fields while splitting columns into separate
        table names for each repeat and then sets the result to a class
        variable
        '''
        for a in json_of_columns_fields:
            table_name = table or 'data'
            if a.get('type') != 'repeat':
                self.flattened_dict[table_name].append(
                    {
                        'name': a.get('name'),
                        'type': self.get_tableau_type(a.get('type'))})
            else:
                table_name = a.get('name')

            # using IGNORED_FIELD_TYPES so that choice values are not included.
            if a.get('children') and a.get('type') not in IGNORED_FIELD_TYPES:
                if a.get('type') == "group":
                    for child in a.get('children'):
                        self.flattened_dict[table_name].append(
                            {
                                "name": a.get('name') + f"_{child['name']}",
                                "type": self.get_tableau_type(child['type'])
                            })
                self.flatten_xform_columns(a.get('children'), table=table_name)

    def get_tableau_column_headers(self):
        """
        Retrieve column headers that are valid in tableau
        """
        tableau_column_headers = defaultdict(list)

        def append_to_tableau_column_headers(
                header, question_type=None, table=None):
            table_name = table or 'data'
            quest_type = question_type or 'string'

            # alias can be updated in the future to question labels
            tableau_column_headers[table_name].append({
                'id': header,
                'dataType': quest_type,
                'alias': header
            })

        # Remove metadata fields from the column headers
        # Calling set to remove duplicates in group data
        xform_headers = set(remove_metadata_fields(self.xform_headers))

        for header in xform_headers:
            for table_name, fields in self.flattened_dict.items():
                for field in fields:
                    if header == field["name"]:
                        append_to_tableau_column_headers(
                            header, field["type"], table_name)
                        break
                    elif 'gps' in field["name"] and 'gps' in header:
                        append_to_tableau_column_headers(
                            header, "string", table_name)
                        break
            else:
                if header == '_id':
                    append_to_tableau_column_headers(header, "int")
                elif header.startswith('meta'):
                    append_to_tableau_column_headers(header)

        # Add repeat parent fields
        for table_name in self.flattened_dict.keys():
            if table_name != 'data':
                append_to_tableau_column_headers(
                    "_id", "int", table_name)
                append_to_tableau_column_headers(
                    "__parent_id", "int", table_name)
                append_to_tableau_column_headers(
                    "__parent_table", table=table_name)

        return tableau_column_headers

    def get_tableau_table_schemas(
            self, column_headers: dict) -> List[dict]:
        ret = []
        project = self.xform.project_id
        id_str = self.xform.id_string
        for table_name, headers in column_headers.items():
            table_schema = {}
            table_schema['table_alias'] = table_name
            table_schema['connection_name'] = f"{project}_{id_str}"
            table_schema['column_headers'] = headers
            if table_name != 'data':
                table_schema['connection_name'] += f"_{table_name}"
            ret.append(table_schema)
        return ret

    @action(methods=['GET'], detail=True)
    def schema(self, request, **kwargs):
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            self.xform = self.object.content_object
            xform_json = json.loads(self.xform.json)
            headers = self.xform.get_headers(repeat_iterations=1)
            self.flatten_xform_columns(xform_json.get('children'))
            self.xform_headers = clean_xform_headers(headers)
            column_headers = self.get_tableau_column_headers()
            data = self.get_tableau_table_schemas(column_headers)
            return Response(data=data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)
