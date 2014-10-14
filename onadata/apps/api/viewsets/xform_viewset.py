import os
import json

from datetime import datetime

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseBadRequest
from django.utils.translation import ugettext as _
from django.utils import six

from rest_framework import exceptions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from onadata.libs import filters
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.renderers import renderers
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.serializers.clone_xform_serializer import \
    CloneXFormSerializer
from onadata.libs.serializers.share_xform_serializer import (
    ShareXFormSerializer)
from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.viewer_tools import enketo_url, EnketoError
from onadata.apps.viewer.models.export import Export
from onadata.libs.exceptions import NoRecordsFoundError
from onadata.libs.utils.export_tools import generate_export,\
    should_create_new_export, generate_external_export
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils import log
from onadata.libs.utils.export_tools import newset_export_for
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.string import str2bool

from onadata.libs.utils.viewer_tools import _get_form_url

EXPORT_EXT = {
    'xls': Export.XLS_EXPORT,
    'xlsx': Export.XLS_EXPORT,
    'csv': Export.CSV_EXPORT,
    'csvzip': Export.CSV_ZIP_EXPORT,
    'savzip': Export.SAV_ZIP_EXPORT,
    'uuid': Export.EXTERNAL_EXPORT,
}

# Supported external exports
external_export_types = ['uuid']


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


def _generate_new_export(request, xform, query, export_type, token=None,
                         meta=None):
    query = _set_start_end_params(request, query)
    extension = _get_extension_from_export_type(export_type)

    try:
        if export_type == Export.EXTERNAL_EXPORT:
            export = generate_external_export(
                export_type, xform.user.username,
                xform.id_string, None, token, query, meta
            )
        else:
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


def _get_user(username):
    users = User.objects.filter(username=username)

    return users.count() and users[0] or None


def _get_owner(request):
    owner = request.DATA.get('owner') or request.user

    if isinstance(owner, six.string_types):
        owner = _get_user(owner)

        if owner is None:
            raise ValidationError(
                u"User with username %(owner)s does not exist."
            )

    return owner


def response_for_format(data, format=None):
    if format == 'xml':
        formatted_data = data.xml
    elif format == 'xls':
        formatted_data = data.xls
    else:
        formatted_data = json.loads(data.json)
    return Response(formatted_data)


def should_regenerate_export(xform, export_type, request):
    return should_create_new_export(xform, export_type) or\
        'start' in request.GET or 'end' in request.GET or\
        'query' in request.GET


def value_for_type(form, field, value):
    if form._meta.get_field(field).get_internal_type() == 'BooleanField':
        return str2bool(value)

    return value


def external_export_response(export):
    if export.internal_status == Export.SUCCESSFUL:
        http_status = status.HTTP_201_CREATED
        data = {"url": export.export_url}
    else:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        data = {"message": export.export_url}

    return Response(data, http_status)


class XFormViewSet(AnonymousUserPublicFormsMixin, LabelsMixin, ModelViewSet):

    """
Publish XLSForms, List, Retrieve Published Forms.

Where:

- `pk` - is the form unique identifier

## Upload XLSForm

To publish and xlsform, you need to provide either the xlsform via `xls_file` \
parameter or a link to the xlsform via the `xls_url` parameter.
Optionally, you can specify the target account where the xlsform should be \
published using the `owner` parameter, which specifies the username to the
account.

- `xls_file`: the xlsform file.
- `xls_url`: the url to an xlsform
- `owner`: username to the target account (Optional)

<pre class="prettyprint">
<b>POST</b> /api/v1/forms</pre>
> Example
>
>       curl -X POST -F xls_file=@/path/to/form.xls \
https://ona.io/api/v1/forms
>
> OR post an xlsform url
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
>           "owner": "ona",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Get list of forms

<pre class="prettyprint">
<b>GET</b> /api/v1/forms</pre>

> Request
>
>       curl -X GET https://ona.io/api/v1/forms


## Get list of forms filter by owner

<pre class="prettyprint">
<b>GET</b> /api/v1/forms?<code>owner</code>=<code>owner_username</code></pre>

> Request
>
>       curl -X GET https://ona.io/api/v1/forms?owner=ona

## Get Form Information

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code></pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058

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
>           "owner": "https://ona.io/api/v1/users/ona",
>           "public": false,
>           "public_data": false,
>           "require_auth": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Set Form Information

You can use `PUT` or `PATCH` http methods to update or set form data elements.
If you are using `PUT`, you have to provide the `uuid, description, owner,
public, public_data` fields. With `PATCH` you only need provide atleast one
of the fields.

<pre class="prettyprint">
<b>PATCH</b> /api/v1/forms/<code>{pk}</code></pre>

> Example
>
>       curl -X PATCH -d "public=True" -d "description=Le description"\
https://ona.io/api/v1/forms/28058

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
>           "description": "Le description",
>           "downloadable": true,
>           "encrypted": false,
>           "owner": "https://ona.io/api/v1/users/ona",
>           "public": true,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Delete Form

<pre class="prettyprint">
<b>DELETE</b> /api/v1/forms/<code>{pk}</code></pre>
> Example
>
>       curl -X DELETE https://ona.io/api/v1/forms/28058
>
> Response
>
>       HTTP 204 NO CONTENT

## List Forms
<pre class="prettyprint">
<b>GET</b> /api/v1/forms
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms

> Response
>
>       [{
>           "url": "https://ona.io/api/v1/forms/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           ...
>       }, ...]

## Get `JSON` | `XML` | `XLS` Form Representation
<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/form.\
<code>{format}</code></pre>
> JSON Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058/form.json

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
>       curl -X GET https://ona.io/api/v1/forms/28058/form.xml

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

> XLS Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058/form.xls

> Response
>
>       Xls file downloaded

## Get list of forms with specific tag(s)

Use the `tags` query parameter to filter the list of forms, `tags` should be a
comma separated list of tags.

<pre class="prettyprint">
<b>GET</b> /api/v1/forms?<code>tags</code>=<code>tag1,tag2</code></pre>

List forms tagged `smart` or `brand new` or both.
> Request
>
>       curl -X GET https://ona.io/api/v1/forms?tag=smart,brand+new

> Response
>        HTTP 200 OK
>
>       [{
>           "url": "https://ona.io/api/v1/forms/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           ...
>       }, ...]


## Get list of Tags for a specific Form
<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/labels
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
<b>POST</b> /api/v1/forms/<code>{pk}</code>/labels
</pre>

Payload

    {"tags": "tag1, tag2"}

## Delete a specific tag

<pre class="prettyprint">
<b>DELETE</b> /api/v1/forms/<code>{pk}</code>/labels/<code>tag_name</code>
</pre>

> Request
>
>       curl -X DELETE \
https://ona.io/api/v1/forms/28058/labels/tag1
>
> or to delete the tag "hello world"
>
>       curl -X DELETE \
https://ona.io/api/v1/forms/28058/labels/hello%20world
>
> Response
>
>        HTTP 200 OK

## Get webform/enketo link

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/enketo</pre>

> Request
>
>       curl -X GET \
https://ona.io/api/v1/forms/28058/enketo
>
> Response
>
>       {"enketo_url": "https://h6ic6.enketo.org/webform"}
>
>        HTTP 200 OK

## Get form data in xls, csv format.

Get form data exported as xls, csv, csv zip, sav zip format.

Where:

- `pk` - is the form unique identifier
- `format` - is the data export format i.e csv, xls, csvzip, savzip

<pre class="prettyprint">
<b>GET</b> /api/v1/exports/{pk}.{format}</code>
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/exports/28058.xls

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

## Share a form with a specific user

You can share a form with a  specific user by `POST` a payload with

- `username` of the user you want to share the form with and
- `role` you want the user to have on the form. Available roles are `readonly`,
`dataentry`, `editor`, `manager`.

<pre class="prettyprint">
<b>POST</b> /api/v1/forms/<code>{pk}</code>/share
</pre>

> Example
>
>       curl -X POST -d '{"username": "alice", "role": "readonly"}' \
https://ona.io/api/v1/forms/123.json

> Response
>
>        HTTP 204 NO CONTENT

## Clone a form to a specific user account

You can clone a form to a specific user account using `GET` with

- `username` of the user you want to clone the form to

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/clone
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/forms/123/clone \
-d username=alice

> Response
>
>        HTTP 201 CREATED
>       {
>           "url": "https://ona.io/api/v1/forms/124",
>           "formid": 124,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1e",
>           "id_string": "Birds_cloned_1",
>           "sms_id_string": "Birds_cloned_1",
>           "title": "Birds_cloned_1",
>           ...
>       }

"""
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.SurveyRenderer
    ]
    queryset = XForm.objects.all()
    serializer_class = XFormSerializer
    lookup_field = 'pk'
    extra_lookup_fields = None
    permission_classes = [XFormPermissions, ]
    updatable_fields = set(('description', 'require_auth',
                            'shared', 'shared_data', 'title'))
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.TagFilter,
                       filters.XFormOwnerFilter)

    public_forms_endpoint = 'public'

    def create(self, request, *args, **kwargs):
        owner = _get_owner(request)
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
        if format not in ['json', 'xml', 'xls']:
            return HttpResponseBadRequest('400 BAD REQUEST',
                                          content_type='application/json',
                                          status=400)
        return response_for_format(form, format=format)

    @action(methods=['GET'])
    def enketo(self, request, **kwargs):
        self.object = self.get_object()
        form_url = _get_form_url(request, self.object.user.username)

        data = {'message': _(u"Enketo not properly configured.")}
        http_status = status.HTTP_400_BAD_REQUEST

        try:
            url = enketo_url(form_url, self.object.id_string)
        except EnketoError:
            pass
        else:
            if url:
                http_status = status.HTTP_200_OK
                data = {"enketo_url": url}

        return Response(data, http_status)

    def retrieve(self, request, *args, **kwargs):
        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)

        if lookup == self.public_forms_endpoint:
            self.object_list = self._get_public_forms_queryset()

            page = self.paginate_queryset(self.object_list)
            if page is not None:
                serializer = self.get_pagination_serializer(page)
            else:
                serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        xform = self.get_object()
        query = request.GET.get("query", {})
        export_type = kwargs.get('format')

        if export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(XFormViewSet, self).retrieve(request, *args, **kwargs)

        export_type = _get_export_type(export_type)
        token = kwargs.get('token')
        meta = kwargs.get('meta')
        if export_type in external_export_types and \
                (token is not None) or (meta is not None):
            export_type = Export.EXTERNAL_EXPORT

        # check if we need to re-generate,
        # we always re-generate if a filter is specified
        if should_regenerate_export(xform, export_type, request):
            export = _generate_new_export(
                request, xform, query, export_type, token, meta)
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

        if export_type == Export.EXTERNAL_EXPORT:
            return external_export_response(export)

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

    @action(methods=['GET'])
    def clone(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = {'xform': self.object.pk, 'username': request.DATA['username']}
        serializer = CloneXFormSerializer(data=data)
        if serializer.is_valid():
            clone_to_user = User.objects.get(username=data['username'])
            if not request.user.has_perm('can_add_xform',
                                         clone_to_user.profile):
                raise exceptions.PermissionDenied(
                    detail=_(u"User %(user)s has no permission to add "
                             "xforms to account %(account)s" %
                             {'user': request.user.username,
                              'account': data['username']}))
            xform = serializer.save()
            serializer = XFormSerializer(
                xform.cloned_form, context={'request': request})

            return Response(data=serializer.data,
                            status=status.HTTP_201_CREATED)

        return Response(data=serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)
