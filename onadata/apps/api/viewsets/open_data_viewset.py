import collections
import json

from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from rest_framework import status

from onadata.apps.logger.models import XForm, Instance
from onadata.apps.logger.models.open_data import OpenData
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.total_header_mixin import TotalHeaderMixin
from onadata.libs.serializers.data_serializer import DataInstanceSerializer
from onadata.apps.api.tools import get_baseviewset_class
from onadata.libs.serializers.open_data_serializer import OpenDataSerializer
from onadata.libs.data import parse_int
from onadata.libs.utils.csv_builder import CSVDataFrameBuilder

BaseViewset = get_baseviewset_class()


def replace_slashes_with_underscores(data, list_of_dicts=True):
    '''
    Replaces slashes with underscores in strings inside a dict or list.
    '''
    if not list_of_dicts:
        return [a.replace('(/', '_') for a in data]

    return [{k.replace('/', '_'): v
             for k, v in dict_obj.items()}
            for dict_obj in data]


class OpenDataViewSet(
        ETagsMixin, CacheControlMixin, TotalHeaderMixin, BaseViewset,
        ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    queryset = OpenData.objects.filter()
    lookup_field = 'uuid'
    serializer_class = OpenDataSerializer
    flattened_dict = {}

    def get_data(self, update=False):
        '''
        return a namedtuple with error, message and data values.
        '''
        request_data = self.request.data
        fields = ['object_id', 'clazz', 'name']
        results = collections.namedtuple('results', 'error message data')
        if not update:
            if not set(fields).issubset(request_data.keys()):
                return results(
                    error=True,
                    message="Fields object_id, clazz and name are required.",
                    data=None
                )

        fields.append('active')

        # check if invalid fields are provided
        if any(a not in fields for a in request_data.keys()):
            return results(
                error=True,
                message="Valid fields are object_id, clazz and name.",
                data=None
            )

        data = {}
        for key in fields:
            available = request_data.get(key) is not None
            available and data.update({key: request_data.get(key)})

        return results(error=False, message=None, data=data)

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
            if a.get('children'):
                self.flattened_dict[a.get('name')] = self.get_tableau_type(
                    a.get('type')
                )
                if a.get('type') not in ['select one', 'select multiple']:
                    self.flatten_xform_columns(a.get('children'))
            else:
                self.flattened_dict[a.get('name')] = self.get_tableau_type(
                    a.get('type')
                )

    def get_tableau_column_headers(self):
        # TODO: may be this is not the best implementation. Suggestions
        # welcomed.
        tableau_colulmn_headers = []
        for header in self.xform_headers:
            found = False
            for quest_name, quest_type in self.flattened_dict.items():
                if header == quest_name or header.endswith('_%s' % quest_name):
                    # alias can be updated in the future to question labels
                    tableau_colulmn_headers.append({
                        'id': header,
                        'dataType': quest_type,
                        'alias': header
                    })
                    found = True
                    break

            if not found:
                tableau_colulmn_headers.append({
                    'id': header,
                    'dataType': 'string',
                    'alias': header
                })

        return tableau_colulmn_headers

    def create(self, request, *args, **kwargs):
        if request.user.is_anonymous():
            return Response(
                'Authentication credentials required.',
                status.HTTP_400_BAD_REQUEST
            )

        results = self.get_data()
        if results.error:
            return Response(results.message, status.HTTP_400_BAD_REQUEST)

        if results.data:
            serializer = OpenDataSerializer(data=results.data)

            if serializer.is_valid():
                _open_data = serializer.save()
                if _open_data:
                    return Response(
                        'Record was successfully created.',
                        status.HTTP_201_CREATED
                    )
            else:
                return Response(
                    str(serializer.errors), status.HTTP_400_BAD_REQUEST
                )

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()
        # get greater than value and cast it to an int
        gt = request.query_params.get('gt_id')
        gt = gt and parse_int(gt)

        data = []
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            qs_kwargs = {'xform': xform}
            if gt:
                qs_kwargs.update({'id__gt': gt})

            instances = Instance.objects.filter(**qs_kwargs)
            csv_df_builder = CSVDataFrameBuilder(
                xform.user.username, xform.id_string, include_images=False
            )
            data = csv_df_builder._format_for_dataframe(
                DataInstanceSerializer(instances, many=True).data
            )
            data = replace_slashes_with_underscores(data)

        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        if request.user.is_anonymous():
            return Response(
                'Authentication credentials required.',
                status.HTTP_400_BAD_REQUEST
            )

        self.object = self.get_object()
        results = self.get_data(update=True)
        if results.error:
            return Response(results.message, status.HTTP_400_BAD_REQUEST)

        if results.data:
            serializer = OpenDataSerializer(self.object, data=results.data)

            if serializer.is_valid():
                _open_data = serializer.save()
                if _open_data:
                    return Response(
                        "Record was successfully updated.",
                        status.HTTP_200_OK
                    )
            else:
                return Response(
                    str(serializer.errors), status.HTTP_400_BAD_REQUEST
                )

        return Response(status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        if request.user.is_anonymous():
            return Response(
                'Authentication credentials required.',
                status.HTTP_400_BAD_REQUEST
            )

        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(methods=['GET'])
    def column_headers(self, request, **kwargs):
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            self.xform_headers = replace_slashes_with_underscores(
                xform.get_headers(), list_of_dicts=False
            )

            xform_json = json.loads(xform.json)
            self.flatten_xform_columns(
                json_of_columns_fields=xform_json.get('children')
            )

            tableau_column_headers = self.get_tableau_column_headers()

            data = {
                'column_headers': tableau_column_headers,
                'connection_name': "%s-%s" % (
                    xform.project_id, xform.id_string
                ),
                'table_alias': xform.title
            }

            return Response(data=data, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_200_OK)

