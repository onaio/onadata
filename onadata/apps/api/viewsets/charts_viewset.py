from django.http import Http404
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
from onadata.libs.serializers.chart_serializer import (
    ChartSerializer, FieldsChartSerializer)
from onadata.libs.utils import common_tags
from onadata.libs.utils.chart_tools import build_chart_data_for_field
from onadata.libs.utils.timing import (
    last_modified_header, get_date, merge_dicts)


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


class ChartsViewSet(AnonymousUserPublicFormsMixin,
                    viewsets.ReadOnlyModelViewSet):

    """
View chart for specific fields in a form or dataset.

### List of chart chart endpoints accessible to registered user
<pre class="prettyprint">
<b>GET</b> /api/v1/charts</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/charts

> Response
>
>        [{
>
>            "id": 4240,
>            "id_string": "dhis2form"
>            "url": "https://ona.io/api/v1/charts/4240",
>        }
>        ...

### Get a list of chart field endpoints for a specific form or dataset.

<pre class="prettyprint">
<b>GET</b> /api/v1/charts/<code>{formid}</code></pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/charts/4240

> Response
>
>        {
>
>            "id": 4240,
>            "id_string": "dhis2form"
>            "url": "https://ona.io/api/v1/charts/4240",
>            "fields": {
>                "uuid": "https://ona.io/api/v1/charts/4240?field_name=uuid",
>                "num": "https://ona.io/api/v1/charts/4240?field_name=num",
>                ...
>            }
>        }

### Get a chart for a specific field in a form

- `field_name` - a field name in the form
- `format` - can be `html` or `json`

<pre class="prettyprint">
<b>GET</b> /api/v1/charts/<code>{formid}</code>.<code>{format}</code>?\
field_name=<code>field_name</code></pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/charts/4240.html?field_name=age

> Response
>
> - `html` format response is a html, javascript and css to the chart
> - `json` format response is the `JSON` data that can be passed to a charting
> library

### Get a chart data for all fields in a form

The only field ommitted is instanceID since it is unique for every record.

- `fields` - is a comma separated list of fields to be included in the \
response. If `fields=all` then all the fields of the form will be returned.

<pre class="prettyprint">
<b>GET</b> /api/v1/charts/<code>{formid}</code>?<code>fields=all</code>
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/charts/4240?fields=all

> Response
>
> - `json` format response is the `JSON` data for each field that can be
> passed to a charting library
    """
    filter_backends = (filters.AnonDjangoObjectPermissionFilter, )
    queryset = XForm.objects.all()
    default_response_headers = last_modified_header(
        get_date(XForm.objects.last(), 'modified'))
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

        self.headers = merge_dicts(
            self.headers, last_modified_header(get_date(xform, 'modified')))
        if fields:
            if fmt is not None and fmt != 'json':
                raise ParseError("Error: only JSON format supported.")

            xform = self.get_object()
            self.headers['Last-Modified'] = get_date(xform, 'modified')
            context = self.get_serializer_context()
            serializer = FieldsChartSerializer(instance=xform, context=context)

            return Response(serializer.data)

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
            choices = dd.survey.get('choices') if dd.survey.get('choices') \
                else None

            if choices:
                choices = choices.get(field_name)

            data = build_chart_data_for_field(
                xform, field, choices=choices)

            if request.accepted_renderer.format == 'json':
                xform = xform.pk
            elif request.accepted_renderer.format == 'html' and 'data' in data:
                for item in data['data']:
                    if isinstance(item[field_name], list):
                        item[field_name] = u', '.join(item[field_name])

            data.update({
                'xform': xform
            })

            return Response(data, template_name='chart_detail.html')

        if fmt != 'json' and field_name is None:
            raise ParseError("Not supported")

        data = serializer.data
        data["fields"] = {}
        for field in dd.survey_elements:
            field_url = get_form_field_chart_url(data["url"], field.name)
            data["fields"][field.name] = field_url

        return Response(data)
