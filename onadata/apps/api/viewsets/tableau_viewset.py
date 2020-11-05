import json
import re
from typing import List

from rest_framework import status
from collections import defaultdict
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.data import parse_int
from onadata.libs.renderers.renderers import pairing
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.api.viewsets.open_data_viewset import (
    OpenDataViewSet)
from onadata.libs.serializers.data_serializer import TableauDataSerializer
from onadata.libs.utils.common_tags import (
    ID, MULTIPLE_SELECT_TYPE, REPEAT_SELECT_TYPE, PARENT_TABLE, PARENT_ID)


DEFAULT_TABLE_NAME = 'data'
GPS_PARTS = ['latitude', 'longitude', 'altitude', 'precision']


def process_tableau_data(
        data, xform,
        parent_table: str = None,
        parent_id: int = None,
        current_table: str = DEFAULT_TABLE_NAME):
    result = []
    if data:
        for idx, row in enumerate(data, start=1):
            flat_dict = defaultdict(list)
            row_id = row.get('_id')

            if not row_id and parent_id:
                row_id = int(pairing(parent_id, idx))
                flat_dict[PARENT_ID] = parent_id
                flat_dict[PARENT_TABLE] = parent_table
                flat_dict[ID] = row_id
            else:
                flat_dict[ID] = row_id

            for (key, value) in row.items():
                qstn = xform.get_element(key)
                if qstn:
                    qstn_type = qstn.get('type')
                    qstn_name = qstn.get('name')

                    prefix_parts = [
                        question['name'] for question in qstn.get_lineage()
                        if question['type'] == 'group'
                    ]
                    prefix = "_".join(prefix_parts)

                    if qstn_type == REPEAT_SELECT_TYPE:
                        repeat_data = process_tableau_data(
                            value, xform,
                            parent_table=current_table,
                            parent_id=row_id,
                            current_table=qstn_name)
                        cleaned_data = unpack_repeat_data(
                            repeat_data, flat_dict)
                        flat_dict[qstn_name] = cleaned_data
                    elif qstn_type == MULTIPLE_SELECT_TYPE:
                        picked_choices = value.split(" ")
                        choice_names = [
                            question["name"] for question in qstn["children"]]
                        list_name = qstn.get('list_name')
                        unpack_select_multiple_data(
                            picked_choices,
                            list_name,
                            choice_names,
                            prefix,
                            flat_dict)
                    elif qstn_type == 'geopoint':
                        gps_parts = unpack_gps_data(
                            value, qstn_name, prefix)
                        flat_dict.update(gps_parts)
                    else:
                        if prefix:
                            qstn_name = f"{prefix}_{qstn_name}"
                        flat_dict[qstn_name] = value
            result.append(dict(flat_dict))
    return result


def unpack_select_multiple_data(picked_choices, list_name,
                                choice_names, prefix, flat_dict):
    for choice in choice_names:
        qstn_name = f"{list_name}_{choice}"

        if prefix:
            qstn_name = prefix + '_' + qstn_name

        if choice in picked_choices:
            flat_dict[qstn_name] = "TRUE"
        else:
            flat_dict[qstn_name] = "FALSE"


def unpack_repeat_data(repeat_data, flat_dict):
    # Pop any list within the returned repeat data.
    # Lists represent a repeat group which should be in a
    # separate field.
    cleaned_data = []
    for data_dict in repeat_data:
        remove_keys = []
        for k, v in data_dict.items():
            if isinstance(v, list):
                remove_keys.append(k)
                flat_dict[k].extend(v)
        # pylint: disable=expression-not-assigned
        [data_dict.pop(k) for k in remove_keys]
        cleaned_data.append(data_dict)
    return cleaned_data


def unpack_gps_data(value, qstn_name, prefix):
    value_parts = value.split(' ')
    gps_xpath_parts = []
    for part in GPS_PARTS:
        name = f"_{qstn_name}_{part}"
        if prefix:
            name = prefix + '_' + name
        gps_xpath_parts.append((name, None))
    if len(value_parts) == 4:
        gps_parts = dict(
            zip(dict(gps_xpath_parts), value_parts))
        return gps_parts


def clean_xform_headers(headers: list) -> list:
    ret = []
    for header in headers:
        if re.search(r"\[+\d+\]", header):
            repeat_count = len(re.findall(r"\[+\d+\]", header))
            header = header.split('/')[repeat_count].replace('[1]', '')

        if not header.endswith('gps'):
            # Replace special character with underscore
            header = re.sub(r"\W", r"_", header)
            ret.append(header)
    return ret


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

    # pylint: disable=arguments-differ
    def flatten_xform_columns(
            self, json_of_columns_fields, table: str = None,
            field_prefix: str = None):
        '''
        Flattens a json of column fields while splitting columns into separate
        table names for each repeat
        '''
        ret = defaultdict(list)
        for field in json_of_columns_fields:
            table_name = table or DEFAULT_TABLE_NAME
            prefix = field_prefix or ""
            field_type = field.get('type')

            if field_type in [REPEAT_SELECT_TYPE, 'group']:
                if field_type == 'repeat':
                    table_name = field.get('name')
                else:
                    prefix = prefix + f"{field['name']}_"

                columns = self.flatten_xform_columns(
                    field.get('children'), table=table_name,
                    field_prefix=prefix)
                for key in columns.keys():
                    ret[key].extend(columns[key])
            elif field_type == MULTIPLE_SELECT_TYPE:
                for option in field.get('children'):
                    list_name = field.get('list_name')
                    option_name = option.get('name')
                    ret[table_name].append(
                        {
                            'name': f'{prefix}{list_name}_{option_name}',
                            'type': self.get_tableau_type('text')
                        }
                    )
            elif field_type == 'geopoint':
                for part in GPS_PARTS:
                    name = f'_{field["name"]}_{part}'
                    if prefix:
                        name = prefix + name
                    ret[table_name].append({
                        'name': name,
                        'type': self.get_tableau_type(field.get('type'))
                    })
            else:
                ret[table_name].append(
                    {
                        'name': prefix + field.get('name'),
                        'type': self.get_tableau_type(field.get('type'))
                    }
                )
        return ret

    def get_tableau_column_headers(self):
        """
        Retrieve column headers that are valid in tableau
        """
        tableau_column_headers = defaultdict(list)
        for table, columns in self.flattened_dict.items():
            # Add ID Fields
            tableau_column_headers[table].append({
                'id': ID,
                'dataType': 'int',
                'alias': ID
            })
            if table != DEFAULT_TABLE_NAME:
                tableau_column_headers[table].append({
                    'id': PARENT_ID,
                    'dataType': 'int',
                    'alias': PARENT_ID
                })
                tableau_column_headers[table].append({
                    'id': PARENT_TABLE,
                    'dataType': 'string',
                    'alias': PARENT_TABLE
                })

            for column in columns:
                tableau_column_headers[table].append({
                    'id': column.get('name'),
                    'dataType': column.get('type'),
                    'alias': column.get('name')
                })
        return tableau_column_headers

    def get_tableau_table_schemas(self) -> List[dict]:
        ret = []
        project = self.xform.project_id
        id_str = self.xform.id_string
        column_headers = self.get_tableau_column_headers()
        for table_name, headers in column_headers.items():
            table_schema = {}
            table_schema['table_alias'] = table_name
            table_schema['connection_name'] = f"{project}_{id_str}"
            table_schema['column_headers'] = headers
            if table_name != DEFAULT_TABLE_NAME:
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
            self.flattened_dict = self.flatten_xform_columns(
                xform_json.get('children'))
            self.xform_headers = clean_xform_headers(headers)
            data = self.get_tableau_table_schemas()
            return Response(data=data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)
