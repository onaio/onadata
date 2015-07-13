from django.core.exceptions import ImproperlyConfigured
from rest_framework import viewsets
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.renderers import (
    TemplateHTMLRenderer, BrowsableAPIRenderer, JSONRenderer)

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.chart_serializer import (
    ChartSerializer, FieldsChartSerializer)
from onadata.libs.utils.chart_tools import get_chart_data_for_field


def get_form_field_chart_url(url, field):
    return u'%s?field_name=%s' % (url, field)


class ChartBrowsableAPIRenderer(BrowsableAPIRenderer):
    """
    View chart for specific fields in a form or dataset.
    """

    def get_default_renderer(self, view):
        """
        Return an instance of the first valid renderer.
        (Don't use another documenting renderer.)
        """
        renderers = [renderer for renderer in view.renderer_classes
                     if not issubclass(renderer, BrowsableAPIRenderer)]
        if not renderers:
            return None
        return renderers[0]()

    def get_content(self, renderer, data,
                    accepted_media_type, renderer_context):

        try:
            content = super(ChartBrowsableAPIRenderer, self).get_content(
                renderer, data, accepted_media_type, renderer_context)
        except ImproperlyConfigured:
            content = super(ChartBrowsableAPIRenderer, self).get_content(
                JSONRenderer(), data, accepted_media_type, renderer_context)

        return content


class ChartsViewSet(AnonymousUserPublicFormsMixin,
                    CacheControlMixin,
                    ETagsMixin,
                    viewsets.ReadOnlyModelViewSet):

    filter_backends = (filters.AnonDjangoObjectPermissionFilter, )
    queryset = XForm.objects.all()
    serializer_class = ChartSerializer
    lookup_field = 'pk'
    renderer_classes = (JSONRenderer,
                        ChartBrowsableAPIRenderer,
                        TemplateHTMLRenderer,
                        )
    permission_classes = [XFormPermissions, ]

    def retrieve(self, request, *args, **kwargs):
        xform = self.get_object()
        serializer = self.get_serializer(xform)
        dd = xform.data_dictionary()

        field_name = request.QUERY_PARAMS.get('field_name')
        fields = request.QUERY_PARAMS.get('fields')
        fmt = kwargs.get('format')

        if fields:
            if fmt is not None and fmt != 'json':
                raise ParseError("Error: only JSON format supported.")

            xform = self.get_object()
            context = self.get_serializer_context()
            serializer = FieldsChartSerializer(instance=xform, context=context)

            return Response(serializer.data)

        if field_name:
            data = get_chart_data_for_field(
                field_name,
                xform,
                fmt
            )

            return Response(data, template_name='chart_detail.html')

        if fmt != 'json' and field_name is None:
            raise ParseError("Not supported")

        data = serializer.data
        data["fields"] = {}
        for field in dd.survey_elements:
            field_url = get_form_field_chart_url(data["url"], field.name)
            data["fields"][field.name] = field_url

        return Response(data)
