from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import authentication
from rest_framework.renderers import TemplateHTMLRenderer, BrowsableAPIRenderer
from onadata.libs.utils import common_tags
from onadata.apps.logger.models import XForm
from onadata.apps.api.tools import get_xform
from onadata.libs.utils.chart_tools import build_chart_data_for_field


class ChartDetail(APIView):
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)
    renderer_classes = (BrowsableAPIRenderer, TemplateHTMLRenderer)
    model = XForm

    def get(self, request, formid, field_name, format=None):
        # TODO: seems like model is taking care of object-level perms,
        # should we just rely on that
        xform = get_xform(formid, request)

        # check if its the special _submission_time META
        if field_name == common_tags.SUBMISSION_TIME:
            field = common_tags.SUBMISSION_TIME
        else:
            # use specified field to get summary
            dd = xform.data_dictionary()
            fields = filter(
                lambda f: f.name == field_name, [e for e in
                                                 dd.survey_elements])

            if len(fields) == 0:
                raise Http404(
                    "Field %s does not not exist on the form" % field_name)

            field = fields[0]

        data = build_chart_data_for_field(xform, field)
        data.update({
            'xform': xform
        })

        return Response(data, template_name='chart_detail.html')
