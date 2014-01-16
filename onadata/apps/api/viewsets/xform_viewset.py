import os
import json

from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import exceptions
from rest_framework import permissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from taggit.forms import TagField

from onadata.apps.api import mixins, serializers
from onadata.apps.api.signals import xform_tags_add, xform_tags_delete
from onadata.apps.api import tools as utils
from onadata.apps.odk_logger.models import XForm
from onadata.libs.utils.viewer_tools import enketo_url
from onadata.apps.odk_viewer.models import Export
from onadata.apps.odk_viewer.pandas_mongo_bridge import NoRecordsFoundError
from onadata.libs.utils.export_tools import generate_export,\
    should_create_new_export
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils import log
from onadata.libs.utils.export_tools import newset_export_for
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name


def _get_form_url(request, username):
    # TODO store strings as constants elsewhere
    if settings.TESTING_MODE:
        http_host = 'testserver.com'
        username = 'bob'
    else:
        http_host = request.META.get('HTTP_HOST') or 'ona.io'

    return 'https://%s/%s' % (http_host, username)

EXPORT_EXT = {
    'xls': Export.XLS_EXPORT,
    'xlsx': Export.XLS_EXPORT,
    'csv': Export.CSV_EXPORT,
    'csvzip': Export.CSV_ZIP_EXPORT,
    'savzip': Export.SAV_ZIP_EXPORT,
}


class XLSRenderer(BaseRenderer):
    media_type = 'application/vnd.openxmlformats'
    format = 'xls'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class XLSXRenderer(XLSRenderer):
    format = 'xlsx'


class CSVRenderer(BaseRenderer):
    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'


class CSVZIPRenderer(BaseRenderer):
    media_type = 'application/octet-stream'
    format = 'csvzip'
    charset = None


class SAVZIPRenderer(BaseRenderer):
    media_type = 'application/octet-stream'
    format = 'savzip'
    charset = None

# TODO add KML, ZIP(attachments) support


class SurveyRenderer(BaseRenderer):
    media_type = 'application/xml'
    format = 'xml'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class XFormViewSet(mixins.MultiLookupMixin, ModelViewSet):
    """
Publish XLSForms, List, Retrieve Published Forms.

Where:

- `owner` - is the organization or user to which the form(s) belong to.
- `pk` - is the project id
- `formid` - is the form id

## Upload XLSForm

<pre class="prettyprint">
<b>GET</b> /api/v1/forms</pre>
> Example
>
>       curl -X POST -F xls_file=@/path/to/form.xls
>       https://ona.io/api/v1/forms
>
> OR
>
>       curl -X POST -d "xls_url=https://ona.io/ukanga/forms/tutorial/form.xls"
>       https://ona.io/api/v1/forms

> Response
>
>       {
>           "url": "https://ona.io/api/v1/forms/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           "allows_sms": false,
>           "bamboo_dataset": "",
>           "description": "",
>           "downloadable": true,
>           "encrypted": false,
>           "is_crowd_form": false,
>           "owner": "modilabs",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }
## Get Form Information

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{formid}</code>
<b>GET</b> /api/v1/projects/<code>{owner}</code>/<code>{pk}</code>/forms/<code>
{formid}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058

> Response
>
>       {
>           "url": "https://ona.io/api/v1/forms/modilabs/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           "allows_sms": false,
>           "bamboo_dataset": "",
>           "description": "",
>           "downloadable": true,
>           "encrypted": false,
>           "is_crowd_form": false,
>           "owner": "https://ona.io/api/v1/users/modilabs",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## List Forms
<pre class="prettyprint">
<b>GET</b> /api/v1/forms
<b>GET</b> /api/v1/forms/<code>{owner}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/modilabs

> Response
>
>       [{
>           "url": "https://ona.io/api/v1/forms/modilabs/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           ...
>       }, ...]

## Get `JSON` | `XML` Form Representation
<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>/form.
<code>{format}</code></pre>
> JSON Example
>
>       curl -X GET https://ona.io/api/v1/forms/modilabs/28058/form.json

> Response
>
>        {
>            "name": "Birds",
>            "title": "Birds",
>            "default_language": "default",
>            "id_string": "Birds",
>            "type": "survey",
>            "children": [
>                {
>                    "type": "text",
>                    "name": "name",
>                    "label": "1. What is your name?"
>                },
>                ...
>                ]
>        }

> XML Example
>
>       curl -X GET https://ona.io/api/v1/forms/modilabs/28058/form.xml

> Response
>
>        <?xml version="1.0" encoding="utf-8"?>
>        <h:html xmlns="http://www.w3.org/2002/xforms" ...>
>          <h:head>
>            <h:title>Birds</h:title>
>            <model>
>              <itext>
>                 .....
>          </h:body>
>        </h:html>

## Get list of forms with specific tag(s)

Use the `tags` query parameter to filter the list of forms, `tags` should be a
comma separated list of tags.

<pre class="prettyprint">
<b>GET</b> /api/v1/forms?<code>tags</code>=<code>tag1,tag2</code>
<b>GET</b> /api/v1/forms/<code>{owner}</code>?<code>tags</code>=<code>
tag1,tag2</code></pre>

List forms tagged `smart` or `brand new` or both.
> Request
>
>       curl -X GET https://ona.io/api/v1/forms?tag=smart,brand+new

> Response
>        HTTP 200 OK
>
>       [{
>           "url": "https://ona.io/api/v1/forms/modilabs/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           ...
>       }, ...]


## Get list of Tags for a specific Form
<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>/labels
</pre>
> Request
>
>       curl -X GET https://ona.io/api/v1/forms/28058/labels

> Response
>
>       ["old", "smart", "clean house"]

## Tag forms

A `POST` payload of parameter `tags` with a comma separated list of tags.

Examples

- `animal fruit denim` - space delimited, no commas
- `animal, fruit denim` - comma delimited

 <pre class="prettyprint">
  <b>POST</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>/labels
  </pre>

Payload

    {"tags": "tag1, tag2"}

## Delete a specific tag

<pre class="prettyprint">
<b>DELETE</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>
/labels/<code>tag_name</code></pre>

> Request
>
>       curl -X DELETE
>       https://ona.io/api/v1/forms/modilabs/28058/labels/tag1
>
> or to delete the tag "hello world"
>
>       curl -X DELETE
>       https://ona.io/api/v1/forms/modilabs/28058/labels/hello%20world
>
> Response
>
>        HTTP 200 OK

## Get webform/enketo link

<pre class="prettyprint">
<b>DELETE</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>
/enketo</pre>

> Request
>
>       curl -X GET
>       https://ona.io/api/v1/forms/modilabs/28058/enketo
>
> Response
>
>       {"enketo_url": "https://h6ic6.enketo.org/webform"}
>
>        HTTP 200 OK

## Get form data in xls, csv format.

Get form data exported as xls, csv, csv zip, sav zip format.

Where:

- `owner` - is the organization or user to which the form(s) belong to.
- `pk` - is the project id
- `formid` - is the form id
- `format` - is the data export format i.e csv, xls, csvzip, savzip

<pre class="prettyprint">
<b>GET</b> /api/v1/exports/<code>{owner}/{formid}.{format}</code>
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/exports/onademo/28058.xls

> binary file export of the format specied is returned as the response for the
> download.
>
> Response
>
>        HTTP 200 OK

"""
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        XLSRenderer, XLSXRenderer, CSVRenderer, CSVZIPRenderer,
        SAVZIPRenderer, SurveyRenderer
    ]
    queryset = XForm.objects.filter()
    serializer_class = serializers.XFormSerializer
    queryset = XForm.objects.all()
    serializer_class = serializers.XFormSerializer
    lookup_fields = ('owner', 'pk')
    lookup_field = 'owner'
    extra_lookup_fields = None
    permission_classes = [permissions.DjangoModelPermissions, ]

    def get_object(self, queryset=None):
        owner, pk = self.lookup_fields
        try:
            if self.kwargs.get(pk, None):
                int(self.kwargs[pk])
                # continue peacefully
        except ValueError:
            self.lookup_fields = ('owner', 'id_string')
            self.kwargs['id_string'] = self.kwargs[pk]
        return super(XFormViewSet, self).get_object(queryset)

    def get_queryset(self):
        owner = self.kwargs.get('owner', None)
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        project_forms = []
        if owner:
            owner = get_object_or_404(User, username=owner)
            if owner != user:
                xfct = ContentType.objects.get(
                    app_label='odk_logger', model='xform')
                xfs = user.userobjectpermission_set.filter(content_type=xfct)
                user_forms = XForm.objects.filter(
                    Q(pk__in=[xf.object_pk for xf in xfs]) | Q(shared=True),
                    user=owner)\
                    .select_related('user')
            else:
                user_forms = owner.xforms.values('pk')
                project_forms = owner.projectxform_set.values('xform')
        else:
            user_forms = user.xforms.values('pk')
            project_forms = user.projectxform_set.values('xform')
        queryset = XForm.objects.filter(
            Q(pk__in=user_forms) | Q(pk__in=project_forms))
        # filter by tags if available.
        tags = self.request.QUERY_PARAMS.get('tags', None)
        if tags and isinstance(tags, basestring):
            tags = tags.split(',')
            queryset = queryset.filter(tags__name__in=tags)
        return queryset.distinct()

    def create(self, request, *args, **kwargs):
        survey = utils.publish_xlsform(request, request.user)
        if isinstance(survey, XForm):
            xform = XForm.objects.get(pk=survey.pk)
            serializer = serializers.XFormSerializer(
                xform, context={'request': request})
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED,
                            headers=headers)
        return Response(survey, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'])
    def form(self, request, format='json', **kwargs):
        self.object = self.get_object()
        if format == 'xml':
            data = self.object.xml
        else:
            data = json.loads(self.object.json)
        return Response(data)

    @action(methods=['GET', 'POST', 'DELETE'], extra_lookup_fields=['label', ])
    def labels(self, request, format='json', **kwargs):
        class TagForm(forms.Form):
            tags = TagField()
        status = 200
        self.object = self.get_object()
        if request.method == 'POST':
            form = TagForm(request.DATA)
            if form.is_valid():
                tags = form.cleaned_data.get('tags', None)
                if tags:
                    for tag in tags:
                        self.object.tags.add(tag)
                    xform_tags_add.send(
                        sender=XForm, xform=self.object, tags=tags)
                    status = 201
        label = kwargs.get('label', None)
        if request.method == 'GET' and label:
            data = [
                tag['name']
                for tag in self.object.tags.filter(name=label).values('name')]
        elif request.method == 'DELETE' and label:
            count = self.object.tags.count()
            self.object.tags.remove(label)
            xform_tags_delete.send(sender=XForm, xform=self.object, tag=label)
            # Accepted, label does not exist hence nothing removed
            if count == self.object.tags.count():
                status = 202
            data = list(self.object.tags.names())
        else:
            data = list(self.object.tags.names())
        return Response(data, status=status)

    @action(methods=['GET'])
    def enketo(self, request, **kwargs):
        self.object = self.get_object()
        form_url = _get_form_url(request, self.object.user.username)
        url = enketo_url(form_url, self.object.id_string)
        data = {'message': _(u"Enketo not properly configured.")}
        status = 400
        if url:
            status = 200
            data = {"enketo_url": url}
        return Response(data, status)

    def retrieve(self, request, *args, **kwargs):
        xform = self.get_object()
        query = request.GET.get("query")
        export_type = kwargs.get('format')
        if export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(XFormViewSet, self).retrieve(request, *args, **kwargs)
        if export_type in EXPORT_EXT.keys():
            export_type = EXPORT_EXT[export_type]
        else:
            raise exceptions.ParseError(
                _(u"'%(export_type)s' format not known or not implemented!" %
                  {'export_type': export_type})
            )
        if export_type == Export.XLS_EXPORT:
            extension = 'xlsx'
        elif export_type in [Export.CSV_ZIP_EXPORT, Export.SAV_ZIP_EXPORT]:
            extension = 'zip'
        else:
            extension = export_type

        audit = {
            "xform": xform.id_string,
            "export_type": export_type
        }
        # check if we need to re-generate,
        # we always re-generate if a filter is specified
        if should_create_new_export(xform, export_type) or query or\
                'start' in request.GET or 'end' in request.GET:
            format_date_for_mongo = lambda x, datetime: datetime.strptime(
                x, '%y_%m_%d_%H_%M_%S').strftime('%Y-%m-%dT%H:%M:%S')
            # check for start and end params
            if 'start' in request.GET or 'end' in request.GET:
                if not query:
                    query = '{}'
                query = json.loads(query)
                query[SUBMISSION_TIME] = {}
                try:
                    if request.GET.get('start'):
                        query[SUBMISSION_TIME]['$gte'] = format_date_for_mongo(
                            request.GET['start'], datetime)
                    if request.GET.get('end'):
                        query[SUBMISSION_TIME]['$lte'] = format_date_for_mongo(
                            request.GET['end'], datetime)
                except ValueError:
                    raise exceptions.ParseError(
                        _("Dates must be in the format YY_MM_DD_hh_mm_ss")
                    )
                else:
                    query = json.dumps(query)
            try:
                export = generate_export(
                    export_type, extension, xform.user.username,
                    xform.id_string, None, query
                )
                log.audit_log(
                    log.Actions.EXPORT_CREATED, request.user, xform.user,
                    _("Created %(export_type)s export on '%(id_string)s'.") %
                    {
                        'id_string': xform.id_string,
                        'export_type': export_type.upper()
                    }, audit, request)
            except NoRecordsFoundError:
                raise Http404(_("No records found to export"))
        else:
            export = newset_export_for(xform, export_type)

        # log download as well
        log.audit_log(
            log.Actions.EXPORT_DOWNLOADED, request.user, xform.user,
            _("Downloaded %(export_type)s export on '%(id_string)s'.") %
            {
                'id_string': xform.id_string,
                'export_type': export_type.upper()
            }, audit, request)

        if not export.filename:
            # tends to happen when using newset_export_for.
            raise Http404("File does not exist!")
        # get extension from file_path, exporter could modify to
        # xlsx if it exceeds limits
        path, ext = os.path.splitext(export.filename)
        ext = ext[1:]
        if request.GET.get('raw'):
            id_string = None
        else:
            id_string = xform.id_string
        response = response_with_mimetype_and_name(
            Export.EXPORT_MIMES[ext], id_string, extension=ext,
            file_path=export.filepath)
        return response
