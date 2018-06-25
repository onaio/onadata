# -*- coding: utf-8 -*-
"""
MergedXFormViewSet: API endpoint for /api/merged-datasets
"""

import json

from django.db.models import Sum
from django.http import HttpResponseBadRequest
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import Instance, MergedXForm
from onadata.libs import filters
from onadata.libs.renderers import renderers
from onadata.libs.serializers.merged_xform_serializer import \
    MergedXFormSerializer


# pylint: disable=too-many-ancestors
class MergedXFormViewSet(mixins.CreateModelMixin,
                         mixins.DestroyModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    """
    Merged XForms viewset: create, list, retrieve, destroy
    """

    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.PublicDatasetsFilter)
    permission_classes = [XFormPermissions]
    queryset = MergedXForm.objects.filter(deleted_at__isnull=True).annotate(
        number_of_submissions=Sum('xforms__num_of_submissions')).all()
    serializer_class = MergedXFormSerializer

    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + \
        [renderers.StaticXMLRenderer]

    # pylint: disable=unused-argument
    @action(methods=['GET'], detail=True)
    def form(self, *args, **kwargs):
        """Return XForm JSON, XLS or XML representing"""

        fmt = kwargs['format']
        if fmt not in ['json', 'xml', 'xls']:
            return HttpResponseBadRequest(
                '400 BAD REQUEST', content_type='application/json', status=400)

        merged_xform = self.get_object()
        data = getattr(merged_xform, fmt)
        if fmt == 'json':
            data = json.loads(data)

        return Response(data)

    # pylint: disable=unused-argument
    @action(methods=['GET'], detail=True)
    def data(self, request, *args, **kwargs):
        """Return data from the merged xforms"""
        merged_xform = self.get_object()
        queryset = Instance.objects.filter(
            xform__in=merged_xform.xforms.all()).order_by('pk')

        return Response(queryset.values_list('json', flat=True))
