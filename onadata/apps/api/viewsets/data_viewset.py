import json
import types
from builtins import str as text

from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.utils import DataError
from django.conf import settings
from django.http import Http404
from django.http import StreamingHttpResponse
from django.utils import six
from django.utils.translation import ugettext as _
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ParseError
from rest_framework.settings import api_settings

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.api.tools import add_tags_to_instance
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models import OsmData, MergedXForm
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.instance import Instance
from onadata.apps.viewer.models.parsed_instance import get_etag_hash_from_query
from onadata.apps.viewer.models.parsed_instance import get_sql_with_params
from onadata.apps.viewer.models.parsed_instance import get_where_clause
from onadata.apps.viewer.models.parsed_instance import query_data
from onadata.libs.exceptions import NoRecordsPermission
from onadata.libs.renderers import renderers
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.data_serializer import DataSerializer
from onadata.libs.serializers.data_serializer import (
    DataInstanceSerializer,
    InstanceHistorySerializer)
from onadata.libs.serializers.data_serializer import JsonDataSerializer
from onadata.libs.serializers.data_serializer import OSMSerializer
from onadata.libs.serializers.geojson_serializer import GeoJsonSerializer
from onadata.libs import filters
from onadata.libs.permissions import CAN_DELETE_SUBMISSION,\
    filter_queryset_xform_meta_perms, filter_queryset_xform_meta_perms_sql
from onadata.libs.exceptions import EnketoError
from onadata.libs.utils.viewer_tools import get_enketo_edit_url
from onadata.libs.utils.api_export_tools import custom_response_handler
from onadata.libs.data import parse_int
from onadata.libs.utils.common_tools import json_stream
from onadata.apps.api.permissions import ConnectViewsetPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.instance import FormInactiveError

SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']
BaseViewset = get_baseviewset_class()


def get_data_and_form(kwargs):
    data_id = text(kwargs.get('dataid'))
    if not data_id.isdigit():
        raise ParseError(_(u"Data ID should be an integer"))

    return (data_id, kwargs.get('format'))


def delete_instance(instance, user):
    """
    Function that calls Instance.set_deleted and catches any exception that may
     occur.
    :param instance:
    :param user:
    :return:
    """
    try:
        instance.set_deleted(timezone.now(), user)
    except FormInactiveError as e:
        raise ParseError(text(e))


class DataViewSet(AnonymousUserPublicFormsMixin,
                  AuthenticateHeaderMixin,
                  ETagsMixin, CacheControlMixin,
                  BaseViewset,
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
        renderers.FLOIPRenderer
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
    pagination_class = StandardPageNumberPagination

    queryset = XForm.objects.filter(deleted_at__isnull=True)

    def get_serializer_class(self):
        pk_lookup, dataid_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)
        fmt = self.kwargs.get('format', self.request.GET.get("format"))
        sort = self.request.GET.get("sort")
        fields = self.request.GET.get("fields")
        if fmt == Attachment.OSM:
            serializer_class = OSMSerializer
        elif fmt == 'geojson':
            serializer_class = GeoJsonSerializer
        elif pk is not None and dataid is None \
                and pk != self.public_data_endpoint:
            if sort or fields:
                serializer_class = JsonDataSerializer
            else:
                serializer_class = DataInstanceSerializer
        else:
            serializer_class = \
                super(DataViewSet, self).get_serializer_class()

        return serializer_class

    def get_object(self, queryset=None):
        obj = super(DataViewSet, self).get_object()
        pk_lookup, dataid_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)

        if pk is not None and dataid is not None:
            try:
                int(dataid)
            except ValueError:
                raise ParseError(_(u"Invalid dataid %(dataid)s"
                                   % {'dataid': dataid}))

            if not obj.is_merged_dataset:
                obj = get_object_or_404(Instance, pk=dataid, xform__pk=pk,
                                        deleted_at__isnull=True)
            else:
                xforms = obj.mergedxform.xforms.filter(deleted_at__isnull=True)
                pks = [xform_id
                       for xform_id in xforms.values_list('pk', flat=True)]

                obj = get_object_or_404(Instance, pk=dataid, xform_id__in=pks,
                                        deleted_at__isnull=True)

        return obj

    def _get_public_forms_queryset(self):
        return XForm.objects.filter(Q(shared=True) | Q(shared_data=True),
                                    deleted_at__isnull=True)

    def _filtered_or_shared_qs(self, qs, pk):
        filter_kwargs = {self.lookup_field: pk}
        qs = qs.filter(**filter_kwargs).only('id', 'shared')

        if not qs:
            filter_kwargs['shared_data'] = True
            qs = XForm.objects.filter(**filter_kwargs).only('id', 'shared')

            if not qs:
                raise Http404(_(u"No data matches with given query."))

        return qs

    def filter_queryset(self, queryset, view=None):
        qs = super(DataViewSet, self).filter_queryset(
            queryset.only('id', 'shared'))
        pk = self.kwargs.get(self.lookup_field)

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
        else:
            tags = self.request.query_params.get('tags')
            not_tagged = self.request.query_params.get('not_tagged')

            if tags and isinstance(tags, six.string_types):
                tags = tags.split(',')
                qs = qs.filter(tags__name__in=tags)
            if not_tagged and isinstance(not_tagged, six.string_types):
                not_tagged = not_tagged.split(',')
                qs = qs.exclude(tags__name__in=not_tagged)

        return qs

    @action(methods=['GET', 'POST', 'DELETE'], detail=True,
            extra_lookup_fields=['label', ])
    def labels(self, request, *args, **kwargs):
        http_status = status.HTTP_400_BAD_REQUEST
        self.object = instance = self.get_object()

        if request.method == 'POST':
            add_tags_to_instance(request, instance)
            http_status = status.HTTP_201_CREATED

        tags = instance.tags
        label = kwargs.get('label')

        if request.method == 'GET' and label:
            data = [tag['name'] for tag in
                    tags.filter(name=label).values('name')]

        elif request.method == 'DELETE' and label:
            count = tags.count()
            tags.remove(label)

            # Accepted, label does not exist hence nothing removed
            http_status = status.HTTP_200_OK if count > tags.count() \
                else status.HTTP_404_NOT_FOUND

            data = list(tags.names())
        else:
            data = list(tags.names())

        if request.method == 'GET':
            http_status = status.HTTP_200_OK

        self.etag_data = data

        return Response(data, status=http_status)

    @action(methods=['GET'], detail=True)
    def enketo(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = {}
        if isinstance(self.object, XForm):
            raise ParseError(_(u"Data id not provided."))
        elif(isinstance(self.object, Instance)):
            if request.user.has_perm("change_xform", self.object.xform):
                return_url = request.query_params.get('return_url')
                if not return_url:
                    raise ParseError(_(u"return_url not provided."))

                try:
                    data["url"] = get_enketo_edit_url(
                        request, self.object, return_url)
                except EnketoError as e:
                    raise ParseError(text(e))
            else:
                raise PermissionDenied(_(u"You do not have edit permissions."))

        self.etag_data = data

        return Response(data=data)

    def destroy(self, request, *args, **kwargs):
        instance_ids = request.data.get('instance_ids')
        self.object = self.get_object()

        if isinstance(self.object, XForm):
            if not instance_ids:
                raise ParseError(_(u"Data id(s) not provided."))
            else:
                instance_ids = [
                    x for x in instance_ids.split(',') if x.isdigit()]

                if not instance_ids:
                    raise ParseError(_(u"Invalid data ids were provided."))

                initial_count = self.object.submission_count()
                Instance.objects.filter(
                    id__in=instance_ids,
                    xform=self.object,
                    # do not update this timestamp when the record have
                    # already been deleted.
                    deleted_at__isnull=True
                ).update(deleted_at=timezone.now())
                # updates the num_of_submissions for the form.
                after_count = self.object.submission_count(force_update=True)
                number_of_records_deleted = initial_count - after_count

                return Response(
                    data={
                        "message":
                        "%d records were deleted" % number_of_records_deleted
                    },
                    status=status.HTTP_200_OK
                )

        elif isinstance(self.object, Instance):

            if request.user.has_perm(
                    CAN_DELETE_SUBMISSION, self.object.xform):
                delete_instance(self.object, request.user)
            else:
                raise PermissionDenied(_(u"You do not have delete "
                                         u"permissions."))

        return Response(status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request, *args, **kwargs):
        data_id, _format = get_data_and_form(kwargs)
        self.object = instance = self.get_object()

        if _format == 'json' or _format is None or _format == 'debug':
            return Response(instance.json)
        elif _format == 'xml':
            return Response(instance.xml)
        elif _format == 'geojson':
            return super(DataViewSet, self)\
                .retrieve(request, *args, **kwargs)
        elif _format == Attachment.OSM:
            serializer = self.get_serializer(instance.osm_data.all())

            return Response(serializer.data)
        else:
            raise ParseError(
                _(u"'%(_format)s' format unknown or not implemented!" %
                  {'_format': _format}))

    @action(methods=['GET'], detail=True)
    def history(self, request, *args, **kwargs):
        data_id, _format = get_data_and_form(kwargs)
        instance = self.get_object()

        # retrieve all history objects and return them
        if _format == 'json' or _format is None or _format == 'debug':
            instance_history = instance.submission_history.all()
            serializer = InstanceHistorySerializer(
                instance_history, many=True)
            return Response(serializer.data)
        else:
            raise ParseError(
                _(u"'%(_format)s' format unknown or not implemented!" %
                  {'_format': _format}))

    def list(self, request, *args, **kwargs):
        fields = request.GET.get("fields")
        query = request.GET.get("query", {})
        sort = request.GET.get("sort")
        start = parse_int(request.GET.get("start"))
        limit = parse_int(request.GET.get("limit"))
        export_type = kwargs.get('format', request.GET.get("format"))
        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)
        is_public_request = lookup == self.public_data_endpoint

        if lookup_field not in list(kwargs):
            self.object_list = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        if is_public_request:
            self.object_list = self._get_public_forms_queryset()
        elif lookup:
            qs = self.filter_queryset(
                self.get_queryset()
            ).values_list('pk', 'is_merged_dataset')
            xform_id, is_merged_dataset = qs[0] if qs else (lookup, False)
            pks = [xform_id]
            if is_merged_dataset:
                xforms = MergedXForm.objects.filter(
                    pk=xform_id, xforms__deleted_at__isnull=True)\
                    .values_list('xforms', flat=True)
                pks = [pk for pk in xforms if pk] or [xform_id]
            self.object_list = Instance.objects.filter(
                xform_id__in=pks, deleted_at=None).only('json').order_by('id')
            xform = self.get_object()
            self.object_list = \
                filter_queryset_xform_meta_perms(xform, request.user,
                                                 self.object_list)
            tags = self.request.query_params.get('tags')
            not_tagged = self.request.query_params.get('not_tagged')

            self.object_list = filters.InstanceFilter(
                self.request.query_params,
                queryset=self.object_list,
                request=request
            ).qs

            if tags and isinstance(tags, six.string_types):
                tags = tags.split(',')
                self.object_list = self.object_list.filter(tags__name__in=tags)
            if not_tagged and isinstance(not_tagged, six.string_types):
                not_tagged = not_tagged.split(',')
                self.object_list = \
                    self.object_list.exclude(tags__name__in=not_tagged)

        if (export_type is None or export_type in ['json', 'jsonp', 'debug']) \
                and hasattr(self, 'object_list'):
            return self._get_data(query, fields, sort, start, limit,
                                  is_public_request)

        xform = self.get_object()
        kwargs = {'instance__xform': xform}

        if export_type == Attachment.OSM:
            if request.GET:
                self.set_object_list(
                    query, fields, sort, start, limit, is_public_request)
                kwargs = {'instance__in': self.object_list}
            osm_list = OsmData.objects.filter(**kwargs).order_by('instance')
            page = self.paginate_queryset(osm_list)
            serializer = self.get_serializer(page)

            return Response(serializer.data)

        elif export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(DataViewSet, self).list(request, *args, **kwargs)

        elif export_type == 'geojson':
            serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        return custom_response_handler(request, xform, query, export_type)

    def set_object_list(
            self, query, fields, sort, start, limit, is_public_request):
        try:
            if not is_public_request:
                xform = self.get_object()

            where, where_params = get_where_clause(query)
            if where:
                self.object_list = self.object_list.extra(where=where,
                                                          params=where_params)

            if (start and limit or limit) and (not sort and not fields):
                start = start if start is not None else 0
                limit = limit if start is None or start == 0 else start + limit
                self.object_list = filter_queryset_xform_meta_perms(
                    self.get_object(), self.request.user, self.object_list)
                self.object_list = self.object_list[start:limit]
            elif (sort or limit or start or fields) and not is_public_request:
                try:
                    query = \
                        filter_queryset_xform_meta_perms_sql(self.get_object(),
                                                             self.request.user,
                                                             query)
                    self.object_list = query_data(xform, query=query,
                                                  sort=sort, start_index=start,
                                                  limit=limit, fields=fields)
                except NoRecordsPermission:
                    self.object_list = []

            if isinstance(self.object_list, QuerySet):
                self.etag_hash = get_etag_hash_from_query(self.object_list)
            else:
                sql, params, records = get_sql_with_params(
                    xform, query=query, sort=sort, start_index=start,
                    limit=limit, fields=fields
                )
                self.etag_hash = get_etag_hash_from_query(records, sql, params)
        except ValueError as e:
            raise ParseError(text(e))
        except DataError as e:
            raise ParseError(text(e))

    def _get_data(self, query, fields, sort, start, limit, is_public_request):
        self.set_object_list(
            query, fields, sort, start, limit, is_public_request)

        pagination_keys = [self.paginator.page_query_param,
                           self.paginator.page_size_query_param]
        query_param_keys = self.request.query_params
        should_paginate = any([k in query_param_keys for k in pagination_keys])
        if not isinstance(self.object_list, types.GeneratorType) and \
                should_paginate:
            self.object_list = self.paginate_queryset(self.object_list)

        STREAM_DATA = getattr(settings, 'STREAM_DATA', False)
        if STREAM_DATA:
            response = self._get_streaming_response()
        else:
            serializer = self.get_serializer(self.object_list, many=True)
            response = Response(serializer.data)

        return response

    def _get_streaming_response(self):
        """
        Get a StreamingHttpResponse response object
        """
        def get_json_string(item):
            return json.dumps(
                item.json if isinstance(item, Instance) else item)

        response = StreamingHttpResponse(
            json_stream(self.object_list, get_json_string),
            content_type="application/json"
        )

        # calculate etag value and add it to response headers
        if hasattr(self, 'etag_hash'):
            self.set_etag_header(None, self.etag_hash)

        # set headers on streaming response
        for k, v in self.headers.items():
            response[k] = v

        return response


class AuthenticatedDataViewSet(DataViewSet):
    permission_classes = (ConnectViewsetPermissions,)
