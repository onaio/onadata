from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import mixins
from rest_framework import generics
from rest_framework import authentication, permissions
from rest_framework.renderers import TemplateHTMLRenderer, BrowsableAPIRenderer
from onadata.libs.utils import common_tags
from onadata.apps.odk_logger.models import XForm
from onadata.apps.api.tools import get_xform, get_form_submissions_grouped_by_field


class ChartDetail(APIView):
    authentication_classes = (authentication.SessionAuthentication, authentication.TokenAuthentication)
    #permission_classes = (permissions.IsAdminUser,)
    renderer_classes = (BrowsableAPIRenderer, TemplateHTMLRenderer)
    model = XForm

    def get(self, request, formid, field_name, format=None):
        # TODO: seems like model is taking care of object-level perms, should we just rely on that
        xform = get_xform(formid, request)

        # This will not be initialized for submission time
        field = None

        # check if its the special _submission_time META
        if field_name == common_tags.SUBMISSION_TIME:
            field_type = 'datetime'
        else:
            # use specified field to get summary
            dd = xform.data_dictionary()
            fields = filter(lambda f: f.name == field_name, [e for e in dd.survey_elements])

            if len(fields) == 0:
                raise Http404("Field {} doesnt not exist on the form".format(field_name))

            field = fields[0]
            # TODO: merge choices with results and set 0's on any missing fields, i.e. they didn't have responses

            field_type = field.type

        result = get_form_submissions_grouped_by_field(xform, field_name)

        if field_type == 'select one':
            # if the field is a select, get a summary of the choices
            choices = [c for c in field.get('children')]

        # numeric, categorized
        data_type_map = {
            'integer': 'numeric',
            'decimal': 'numeric',
            'datetime': 'time',
            'date': 'time',
            'start': 'time',
            'end': 'time'
        }
        data_type = data_type_map.get(field_type, 'categorized')

        data = {
            'xform': xform,
            'field_name': field_name,
            'field_type': field_type,
            'data_type': data_type,
            'data': result
        }
        return Response(data, template_name='chart_detail.html')