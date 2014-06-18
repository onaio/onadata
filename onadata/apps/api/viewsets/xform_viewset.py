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
from django.utils import six

from rest_framework import exceptions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from taggit.forms import TagField

from onadata.libs.mixins.multi_lookup_mixin import MultiLookupMixin
from onadata.libs.models.signals import xform_tags_add, xform_tags_delete
from onadata.libs.renderers import renderers
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.serializers.share_xform_serializer import (
    ShareXFormSerializer)
from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import XForm
from onadata.libs.utils.viewer_tools import enketo_url
from onadata.apps.viewer.models import Export
from onadata.apps.viewer.pandas_mongo_bridge import NoRecordsFoundError
from onadata.libs.utils.export_tools import generate_export,\
    should_create_new_export
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils import log
from onadata.libs.utils.export_tools import newset_export_for
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.string import str2bool

EXPORT_EXT = {
    'xls': Export.XLS_EXPORT,
    'xlsx': Export.XLS_EXPORT,
    'csv': Export.CSV_EXPORT,
    'csvzip': Export.CSV_ZIP_EXPORT,
    'savzip': Export.SAV_ZIP_EXPORT,
}


def _get_export_type(export_type):
    if export_type in EXPORT_EXT.keys():
        export_type = EXPORT_EXT[export_type]
    else:
        raise exceptions.ParseError(
            _(u"'%(export_type)s' format not known or not implemented!" %
              {'export_type': export_type})
        )

    return export_type


def _get_extension_from_export_type(export_type):
    extension = export_type

    if export_type == Export.XLS_EXPORT:
        extension = 'xlsx'
    elif export_type in [Export.CSV_ZIP_EXPORT, Export.SAV_ZIP_EXPORT]:
        extension = 'zip'

    return extension


class TagForm(forms.Form):
    tags = TagField()


def _labels_post(request, xform):
    """Process a post request to labels.

    :param request: The HTTP request to extract data from.
    :param xform: The XForm to interact with.
    :returns: A HTTP status code or None.
    """
    form = TagForm(request.DATA)

    if form.is_valid():
        tags = form.cleaned_data.get('tags', None)

        if tags:
            for tag in tags:
                xform.tags.add(tag)
            xform_tags_add.send(
                sender=XForm, xform=xform, tags=tags)

            return 201


def _labels_delete(label, xform):
    count = xform.tags.count()
    xform.tags.remove(label)
    xform_tags_delete.send(sender=XForm, xform=xform, tag=label)

    # Accepted, label does not exist hence nothing removed
    http_status = status.HTTP_202_ACCEPTED if count == xform.tags.count()\
        else status.HTTP_200_OK

    return [http_status, list(xform.tags.names())]


def _set_start_end_params(request, query):
    format_date_for_mongo = lambda x, datetime: datetime.strptime(
        x, '%y_%m_%d_%H_%M_%S').strftime('%Y-%m-%dT%H:%M:%S')

    # check for start and end params
    if 'start' in request.GET or 'end' in request.GET:
        query = json.loads(query) \
            if isinstance(query, six.string_types) else query
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

        return query


def _generate_new_export(request, xform,  query, export_type):
    query = _set_start_end_params(request, query)
    extension = _get_extension_from_export_type(export_type)

    try:
        export = generate_export(
            export_type, extension, xform.user.username,
            xform.id_string, None, query
        )
        audit = {
            "xform": xform.id_string,
            "export_type": export_type
        }
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
        return export


def _get_form_url(request, username):
    # TODO store strings as constants elsewhere
    if settings.TESTING_MODE:
        http_host = 'testserver.com'
        username = 'bob'
    else:
        http_host = request.META.get('HTTP_HOST', 'ona.io')

    return 'https://%s/%s' % (http_host, username)


def _get_user(username):
    users = User.objects.filter(username=username)

    return users.count() and users[0] or None


def response_for_format(data, format=None):
    formatted_data = data.xml if format == 'xml' else json.loads(data.json)
    return Response(formatted_data)


def should_regenerate_export(xform, export_type, request):
    return should_create_new_export(xform, export_type) or\
        'start' in request.GET or 'end' in request.GET or\
        'query' in request.GET


def value_for_type(form, field, value):
    if form._meta.get_field(field).get_internal_type() == 'BooleanField':
        return str2bool(value)

    return value


class XFormViewSet(MultiLookupMixin, ModelViewSet):
    """
Publish XLSForms, List, Retrieve Published Forms.

Where:

- `owner` - is the organization or user to which the form(s) belong to.
- `formid` - is the form id

## Upload XLSForm

<pre class="prettyprint">
<b>POST</b> /api/v1/forms</pre>
> Example
>
>       curl -X POST -F xls_file=@/path/to/form.xls \
https://ona.io/api/v1/forms
>
> OR
>
>       curl -X POST -d \
"xls_url=https://ona.io/ukanga/forms/tutorial/form.xls" \
https://ona.io/api/v1/forms

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
>           "owner": "modilabs",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }
## Get Form Information

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{formid}</code></pre>

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
>           "owner": "https://ona.io/api/v1/users/modilabs",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Set Form Information

You can use `PUT` or `PATCH` http methods to update or set form data elements.
If you are using `PUT`, you have to provide the `uuid, description, owner,
public, public_data` fields. With `PATCH` you only need provide atleast one
of the fields.

<pre class="prettyprint">
<b>PATCH</b> /api/v1/forms/<code>{formid}</code></pre>

> Example
>
>       curl -X PATCH -d "public=True" -d "description=Le description"\
https://ona.io/api/v1/forms/28058

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
>           "description": "Le description",
>           "downloadable": true,
>           "encrypted": false,
>           "owner": "https://ona.io/api/v1/users/modilabs",
>           "public": true,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Delete Form

<pre class="prettyprint">
<b>DELETE</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code></pre>

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
<b>GET</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>/form.\
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
<b>GET</b> /api/v1/forms/<code>{owner}</code>?<code>tags</code>=<code>\
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
<b>DELETE</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>\
/labels/<code>tag_name</code></pre>

> Request
>
>       curl -X DELETE \
https://ona.io/api/v1/forms/modilabs/28058/labels/tag1
>
> or to delete the tag "hello world"
>
>       curl -X DELETE \
https://ona.io/api/v1/forms/modilabs/28058/labels/hello%20world
>
> Response
>
>        HTTP 200 OK

## Get webform/enketo link

<pre class="prettyprint">
<b>DELETE</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>\
/enketo</pre>

> Request
>
>       curl -X GET \
https://ona.io/api/v1/forms/modilabs/28058/enketo
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

## Get list of public forms

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/public
</pre>

## Get list of a users/organization's public forms

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{owner}</code>public
</pre>

## Share a form with a specific user

You can share a form with a  specific user by `POST` a payload with

- `username` of the user you want to share the form with and
- `role` you want the user to have on the form. Availabel roles are `readonly`,
`dataentry`, `editor`, `manager`.

<pre class="prettyprint">
<b>POST</b> /api/v1/forms/<code>{owner}</code>/<code>{formid}</code>/share
</pre>

> Example
>
>       curl -X POST -d '{"username": "alice", "role": "readonly"}' \
https://ona.io/api/v1/forms/onademo/123.json

> Response
>
>        HTTP 204
"""
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.SurveyRenderer
    ]
    queryset = XForm.objects.filter()
    serializer_class = XFormSerializer
    queryset = XForm.objects.all()
    serializer_class = XFormSerializer
    lookup_fields = ('owner', 'pk')
    lookup_field = 'owner'
    extra_lookup_fields = None
    permission_classes = [XFormPermissions, ]
    updatable_fields = set(('description', 'shared', 'shared_data', 'title'))

    def get_object(self, queryset=None):
        owner, pk = self.lookup_fields

        try:
            int(self.kwargs[pk])
        except ValueError:
            # implies pk is a string, assume this represents the id_string
            self.lookup_fields = ('owner', 'id_string')
            self.kwargs['id_string'] = self.kwargs[pk]

        return super(XFormViewSet, self).get_object(queryset)

    def get_queryset(self):
        owner, pk = self.lookup_fields

        owner = self.kwargs.get(owner, None)
        user = self.request.user \
            if not self.request.user.is_anonymous() \
            else User.objects.get(pk=-1)
        project_forms = []

        if isinstance(owner, six.string_types) and owner == 'public':
            user_forms = XForm.objects.filter(
                Q(shared=True) | Q(shared_data=True))
        elif isinstance(owner, six.string_types) and owner != 'public':
            owner = get_object_or_404(User, username=owner)
            if owner != user:
                xfct = ContentType.objects.get(
                    app_label='logger', model='xform')
                xfs = user.userobjectpermission_set.filter(content_type=xfct)
                user_forms = XForm.objects.filter(
                    Q(pk__in=[xf.object_pk for xf in xfs]) | Q(shared=True)
                    | Q(shared_data=True),
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

        if tags and isinstance(tags, six.string_types):
            tags = tags.split(',')
            queryset = queryset.filter(tags__name__in=tags)

        return queryset.distinct()

    def create(self, request, *args, **kwargs):
        owner = _get_user(kwargs.get('owner')) or request.user
        survey = utils.publish_xlsform(request, owner)

        if isinstance(survey, XForm):
            xform = XForm.objects.get(pk=survey.pk)
            serializer = XFormSerializer(
                xform, context={'request': request})
            headers = self.get_success_headers(serializer.data)

            return Response(serializer.data, status=status.HTTP_201_CREATED,
                            headers=headers)

        return Response(survey, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'])
    def form(self, request, format='json', **kwargs):
        form = self.get_object()

        return response_for_format(form, format=format)

    @action(methods=['GET', 'POST', 'DELETE'], extra_lookup_fields=['label', ])
    def labels(self, request, format='json', **kwargs):
        http_status = status.HTTP_200_OK
        xform = self.get_object()

        if request.method == 'POST':
            http_status = _labels_post(request, xform)

        label = kwargs.get('label', None)

        if request.method == 'GET' and label:
            data = [tag['name']
                    for tag in xform.tags.filter(name=label).values('name')]
        elif request.method == 'DELETE' and label:
            http_status, data = _labels_delete(label, xform)
        else:
            data = list(xform.tags.names())

        return Response(data, status=http_status)

    @action(methods=['GET'])
    def enketo(self, request, **kwargs):
        self.object = self.get_object()
        form_url = _get_form_url(request, self.object.user.username)
        url = enketo_url(form_url, self.object.id_string)
        data = {'message': _(u"Enketo not properly configured.")}
        http_status = status.HTTP_400_BAD_REQUEST

        if url:
            http_status = status.HTTP_200_OK
            data = {"enketo_url": url}

        return Response(data, http_status)

    def retrieve(self, request, *args, **kwargs):
        owner, pk = self.lookup_fields

        if self.kwargs.get(pk) == 'public':
            return self.public(request, *args, **kwargs)

        xform = self.get_object()
        query = request.GET.get("query", {})
        export_type = kwargs.get('format')

        if export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(XFormViewSet, self).retrieve(request, *args, **kwargs)

        export_type = _get_export_type(export_type)

        # check if we need to re-generate,
        # we always re-generate if a filter is specified
        if should_regenerate_export(xform, export_type, request):
            export = _generate_new_export(request, xform, query, export_type)
        else:
            export = newset_export_for(xform, export_type)

        # log download as well
        audit = {
            "xform": xform.id_string,
            "export_type": export_type
        }
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
        id_string = None if request.GET.get('raw') else xform.id_string
        response = response_with_mimetype_and_name(
            Export.EXPORT_MIMES[ext], id_string, extension=ext,
            file_path=export.filepath)

        return response

    def public(self, request, *args, **kwargs):
        self.object_list = self.filter_queryset(self.get_queryset()).filter(
            Q(shared=True) | Q(shared_data=True))

        # Switch between paginated or standard style responses
        page = self.paginate_queryset(self.object_list)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(self.object_list, many=True)

        return Response(serializer.data)

    @action(methods=['POST'])
    def share(self, request, *args, **kwargs):
        self.object = self.get_object()

        data = {}
        for key, val in request.DATA.iteritems():
            data[key] = val
        data.update({'xform': self.object.pk})

        serializer = ShareXFormSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)
