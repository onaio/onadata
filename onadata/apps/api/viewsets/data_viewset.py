from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import six
from django.utils.translation import ugettext as _
from django.core.exceptions import PermissionDenied

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import BasePaginationSerializer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ParseError
from rest_framework.settings import api_settings

from onadata.apps.api.viewsets.xform_viewset import custom_response_handler
from onadata.apps.api.tools import add_tags_to_instance
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.instance import Instance
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.renderers import renderers
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.apps.api.permissions import XFormPermissions
from onadata.libs.serializers.data_serializer import DataSerializer
from onadata.libs.serializers.data_serializer import DataListSerializer
from onadata.libs.serializers.data_serializer import OSMSerializer
from onadata.libs.serializers.geojson_serializer import GeoJsonSerializer
from onadata.libs.serializers.geojson_serializer import GeoJsonListSerializer
from onadata.libs import filters
from onadata.libs.utils.viewer_tools import (
    EnketoError,
    get_enketo_edit_url)


SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']


class CustomPaginationSerializer(BasePaginationSerializer):
    def to_native(self, obj):
        ret = self._dict_class()
        ret.fields = self._dict_class()
        results = super(CustomPaginationSerializer, self).to_native(obj)

        if results:
            ret = results[self.results_field]

        return ret


class DataViewSet(AnonymousUserPublicFormsMixin,
                  LastModifiedMixin,
                  ModelViewSet):
    """
    This endpoint provides access to submitted data.
    """
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.SurveyRenderer,
        renderers.GeoJsonRenderer,
        renderers.KMLRenderer,
        renderers.OSMRenderer,
    ]

    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.XFormOwnerFilter,
                       filters.DataFilter)
    serializer_class = DataSerializer
    permission_classes = (XFormPermissions,)
    lookup_field = 'pk'
    lookup_fields = ('pk', 'dataid')
    extra_lookup_fields = None
    public_data_endpoint = 'public'
    pagination_serializer_class = CustomPaginationSerializer
    paginate_by = 1000000
    paginate_by_param = 'page_size'
    page_kwarg = 'page'

    queryset = XForm.objects.all()

    def get_serializer_class(self):
        pk_lookup, dataid_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)
        fmt = self.kwargs.get('format')
        if fmt == Attachment.OSM:
            serializer_class = OSMSerializer
        elif pk is not None and dataid is None \
                and pk != self.public_data_endpoint:
            serializer_class = DataListSerializer
        else:
            serializer_class = \
                super(DataViewSet, self).get_serializer_class()

        return serializer_class

    def get_object(self, queryset=None):
        obj = super(DataViewSet, self).get_object(queryset)
        pk_lookup, dataid_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)

        if pk is not None and dataid is not None:
            try:
                int(dataid)
            except ValueError:
                raise ParseError(_(u"Invalid dataid %(dataid)s"
                                   % {'dataid': dataid}))

            obj = get_object_or_404(Instance, pk=dataid, xform__pk=pk)

        return obj

    def _get_public_forms_queryset(self):
        return XForm.objects.filter(Q(shared=True) | Q(shared_data=True))

    def _filtered_or_shared_qs(self, qs, pk):
        filter_kwargs = {self.lookup_field: pk}
        qs = qs.filter(**filter_kwargs)

        if not qs:
            filter_kwargs['shared_data'] = True
            qs = XForm.objects.filter(**filter_kwargs)

            if not qs:
                raise Http404(_(u"No data matches with given query."))

        return qs

    def filter_queryset(self, queryset, view=None):
        qs = super(DataViewSet, self).filter_queryset(queryset)
        pk = self.kwargs.get(self.lookup_field)
        tags = self.request.QUERY_PARAMS.get('tags', None)

        if tags and isinstance(tags, six.string_types):
            tags = tags.split(',')
            qs = qs.filter(tags__name__in=tags).distinct()

        if pk:
            try:
                int(pk)
            except ValueError:
                if pk == self.public_data_endpoint:
                    qs = self._get_public_forms_queryset()
                else:
                    raise ParseError(_(u"Invalid pk %(pk)s" % {'pk': pk}))
            else:
                qs = self._filtered_or_shared_qs(qs, pk)

        return qs

    @action(methods=['GET', 'POST', 'DELETE'], extra_lookup_fields=['label', ])
    def labels(self, request, *args, **kwargs):
        http_status = status.HTTP_400_BAD_REQUEST
        instance = self.get_object()

        if request.method == 'POST':
            if add_tags_to_instance(request, instance):
                http_status = status.HTTP_201_CREATED

        tags = instance.tags
        label = kwargs.get('label', None)

        if request.method == 'GET' and label:
            data = [tag['name'] for tag in
                    tags.filter(name=label).values('name')]

        elif request.method == 'DELETE' and label:
            count = tags.count()
            tags.remove(label)

            # Accepted, label does not exist hence nothing removed
            http_status = status.HTTP_200_OK if count == tags.count() \
                else status.HTTP_404_NOT_FOUND

            data = list(tags.names())
        else:
            data = list(tags.names())

        if request.method == 'GET':
            http_status = status.HTTP_200_OK

        return Response(data, status=http_status)

    @action(methods=['GET'])
    def enketo(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = {}
        if isinstance(self.object, XForm):
            raise ParseError(_(u"Data id not provided."))
        elif(isinstance(self.object, Instance)):
            if request.user.has_perm("change_xform", self.object.xform):
                return_url = request.QUERY_PARAMS.get('return_url')
                if not return_url:
                    raise ParseError(_(u"return_url not provided."))

                try:
                    data["url"] = get_enketo_edit_url(
                        request, self.object, return_url)
                except EnketoError as e:
                    data['detail'] = "{}".format(e)
            else:
                raise PermissionDenied(_(u"You do not have edit permissions."))

        return Response(data=data)

    def destroy(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(self.object, XForm):
            raise ParseError(_(u"Data id not provided."))
        elif isinstance(self.object, Instance):

            if request.user.has_perm("delete_xform", self.object.xform):
                self.object.delete()
            else:
                raise PermissionDenied(_(u"You do not have delete "
                                         u"permissions."))

        return Response(status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request, *args, **kwargs):
        data_id = str(kwargs.get('dataid'))
        _format = kwargs.get('format')

        if not data_id.isdigit():
            raise ParseError(_(u"Data ID should be an integer"))

        try:
            instance = self.get_object()

            if _format == 'json' or _format is None:
                return Response(instance.json)
            elif _format == 'xml':
                return Response(instance.xml)
            elif _format == 'geojson':
                query_params = (request and request.QUERY_PARAMS) or {}

                data = {"instance": instance,
                        "geo_field": query_params.get('geo_field'),
                        "fields": query_params.get('fields')}

                serializer = GeoJsonSerializer(data)

                return Response(serializer.data)
            elif _format == Attachment.OSM:
                serializer = self.get_serializer(instance)

                return Response(serializer.data)
            else:
                raise ParseError(
                    _(u"'%(_format)s' format unknown or not implemented!" %
                      {'_format': _format})
                )
        except Instance.DoesNotExist:
            raise ParseError(
                _(u"data with id '%(data_id)s' not found!" %
                  {'data_id': data_id})
            )

    def list(self, request, *args, **kwargs):
        query = request.GET.get("query", {})
        export_type = kwargs.get('format')
        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)

        if lookup_field not in kwargs.keys():
            self.object_list = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        if lookup == self.public_data_endpoint:
            self.object_list = self._get_public_forms_queryset()
        elif lookup:
            qs = self.filter_queryset(self.get_queryset())
            self.object_list = Instance.objects.filter(xform__in=qs)

        if (export_type is None or export_type in ['json']) \
                and hasattr(self, 'object_list'):

            where, where_params = ParsedInstance._get_where_clause(query)

            if where:
                self.object_list = self.object_list.extra(where=where,
                                                          params=where_params)

            page = self.paginate_queryset(self.object_list)
            if page is not None:
                serializer = self.get_pagination_serializer(page)
            else:
                serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        xform = self.get_object()
        query = request.GET.get("query", {})
        export_type = kwargs.get('format')

        if export_type == Attachment.OSM:
            serializer = self.get_serializer(self.object_list, many=True)
            return Response(serializer.data)
        elif export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(DataViewSet, self).list(request, *args, **kwargs)
        elif export_type == 'geojson':
            self.object_list = self.filter_queryset(self.get_queryset())
            query_params = (request and request.QUERY_PARAMS) or {}

            data = {"instances": self.object_list,
                    "geo_field": query_params.get('geo_field'),
                    "fields": query_params.get('fields')}

            serializer = GeoJsonListSerializer(data)

            return Response(serializer.data)

        return custom_response_handler(request, xform, query, export_type)
