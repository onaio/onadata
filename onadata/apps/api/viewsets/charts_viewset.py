from django.http import Http404
from django.core.exceptions import ImproperlyConfigured
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.renderers import (
    TemplateHTMLRenderer, BrowsableAPIRenderer, JSONRenderer)

from onadata.apps.logger.models.xform import XForm
from onadata.libs.serializers.chart_serializer import ChartSerializer
from onadata.libs.utils import common_tags
from onadata.libs.utils.chart_tools import build_chart_data_for_field


def get_form_field_chart_url(url, field):
    return u'%s?field_name=%s' % (url, field)


class ChartBrowsableAPIRenderer(BrowsableAPIRenderer):

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


class ChartsViewset(viewsets.ReadOnlyModelViewSet):
    model = XForm
    serializer_class = ChartSerializer
    lookup_field = 'pk'
    renderer_classes = (ChartBrowsableAPIRenderer,
                        TemplateHTMLRenderer,
                        JSONRenderer,
                        )

    def retrieve(self, request, *args, **kwargs):
        xform = self.get_object()
        serializer = self.get_serializer(xform)
        dd = xform.data_dictionary()

        field_name = request.QUERY_PARAMS.get('field_name')

        if field_name:
            # check if its the special _submission_time META
            if field_name == common_tags.SUBMISSION_TIME:
                field = common_tags.SUBMISSION_TIME
            else:
                # use specified field to get summary
                fields = filter(
                    lambda f: f.name == field_name,
                    [e for e in dd.survey_elements])

                if len(fields) == 0:
                    raise Http404(
                        "Field %s does not not exist on the form" % field_name)

                field = fields[0]

            data = build_chart_data_for_field(xform, field)

            if request.accepted_renderer.format == 'json':
                xform = xform.pk

            data.update({
                'xform': xform
            })

            return Response(data, template_name='chart_detail.html')

        data = serializer.data
        data["fields"] = {}
        for field in dd.survey_elements:
            field_url = get_form_field_chart_url(data["url"], field.name)
            data["fields"][field.name] = field_url

        return Response(data)
