# -*- coding: utf-8 -*-
"""
Expose and persist charts and corresponding data.
"""

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import WidgetViewSetPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget
from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.widget_serializer import WidgetSerializer

BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class WidgetViewSet(
    AuthenticateHeaderMixin, CacheControlMixin, ETagsMixin, BaseViewset, ModelViewSet
):
    """
    Expose and persist charts and corresponding data.
    """

    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [WidgetViewSetPermissions]
    lookup_field = "pk"
    filter_backends = (filters.WidgetFilter,)

    def filter_queryset(self, queryset):
        dataviewid = self.request.query_params.get("dataview")

        if dataviewid:
            try:
                int(dataviewid)
            except ValueError as exc:
                raise ParseError(f"Invalid value for dataview {dataviewid}.") from exc

            dataview = get_object_or_404(
                DataView,
                pk=dataviewid,
                xform__deleted_at__isnull=True,
                xform__project__organization__is_active=True,
                project__deleted_at__isnull=True,
                project__organization__is_active=True,
            )
            dataview_ct = ContentType.objects.get_for_model(dataview)
            dataview_qs = Widget.objects.filter(
                object_id=dataview.pk, content_type=dataview_ct
            )
            return dataview_qs

        return super().filter_queryset(queryset)

    @staticmethod
    def _check_active_widget_target(widget):
        content_object = widget.content_object
        if isinstance(content_object, DataView):
            xform = content_object.xform
        elif isinstance(content_object, XForm):
            xform = content_object
        else:
            return

        if xform.deleted_at is not None or not xform.project.organization.is_active:
            raise Http404

    # pylint: disable=unused-argument
    def get_object(self, queryset=None):
        widget_pk = self.kwargs.get("pk")

        if widget_pk is not None:
            obj = get_object_or_404(Widget, pk=widget_pk)
            self._check_active_widget_target(obj)
            self.check_object_permissions(self.request, obj)
        else:
            raise ParseError(_("'pk' required for this action"))

        return obj

    def list(self, request, *args, **kwargs):
        if "key" in request.GET:
            key = request.GET["key"]
            obj = get_object_or_404(Widget, key=key)
            self._check_active_widget_target(obj)

            serializer = self.get_serializer(obj)

            return Response(serializer.data)

        return super().list(request, *args, **kwargs)
