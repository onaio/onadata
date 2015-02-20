import os
import json

from datetime import datetime

from celery.result import AsyncResult
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.contrib.auth.models import User
from django.conf import settings
from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.utils import six
from django.utils import timezone

from rest_framework import exceptions
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.decorators import action, detail_route, list_route
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from onadata.apps.main.views import get_enketo_preview_url
from onadata.apps.api import tasks
from onadata.apps.viewer import tasks as viewer_task
from onadata.libs import filters
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
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
from onadata.libs.exceptions import NoRecordsFoundError, J2XException
from onadata.libs.utils.export_tools import generate_export,\
    should_create_new_export, generate_external_export, generate_kml_export
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils import log
from onadata.libs.utils.export_tools import newset_export_for
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.string import str2bool

from onadata.libs.utils.csv_import import get_async_csv_submission_status
from onadata.libs.utils.csv_import import submit_csv
from onadata.libs.utils.csv_import import submit_csv_async
from onadata.libs.utils.viewer_tools import _get_form_url


EXPORT_EXT = {
    'xls': Export.XLS_EXPORT,
    'xlsx': Export.XLS_EXPORT,
    'csv': Export.CSV_EXPORT,
    'csvzip': Export.CSV_ZIP_EXPORT,
    'savzip': Export.SAV_ZIP_EXPORT,
    'uuid': Export.EXTERNAL_EXPORT,
    'kml': Export.KML_EXPORT,

}

# Supported external exports
external_export_types = ['xls']


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


def _format_date_for_mongo(x, datetime):
    return datetime.strptime(
        x, '%y_%m_%d_%H_%M_%S').strftime('%Y-%m-%dT%H:%M:%S')


def _set_start_end_params(request, query):
    # check for start and end params
    if 'start' in request.GET or 'end' in request.GET:
        query = json.loads(query) \
            if isinstance(query, six.string_types) else query
        query[SUBMISSION_TIME] = {}

        try:
            if request.GET.get('start'):
                query[SUBMISSION_TIME]['$gte'] = _format_date_for_mongo(
                    request.GET['start'], datetime)

            if request.GET.get('end'):
                query[SUBMISSION_TIME]['$lte'] = _format_date_for_mongo(
                    request.GET['end'], datetime)
        except ValueError:
            raise exceptions.ParseError(
                _("Dates must be in the format YY_MM_DD_hh_mm_ss")
            )
        else:
            query = json.dumps(query)

        return query


def _generate_new_export(request, xform, query, export_type):
    query = _set_start_end_params(request, query)
    extension = _get_extension_from_export_type(export_type)

    try:
        if export_type == Export.EXTERNAL_EXPORT:
            export = generate_external_export(
                export_type, xform.user.username,
                xform.id_string, None, request.GET.get('token'), query,
                request.GET.get('meta'), request.GET.get('data_id')
            )
        elif export_type == Export.KML_EXPORT:
            export = generate_kml_export(
                export_type, extension, xform.user.username,
                xform.id_string, export_id=None, filter_query=None)
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
    except J2XException as e:
        # j2x exception
        return {'error': str(e)}
    else:
        return export


def _get_user(username):
    users = User.objects.filter(username=username)

    return users.count() and users[0] or None


def _get_owner(request):
    owner = request.DATA.get('owner') or request.user

    if isinstance(owner, six.string_types):
        owner_obj = _get_user(owner)

        if owner_obj is None:
            raise ValidationError(
                u"User with username %s does not exist." % owner)
        else:
            owner = owner_obj

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
        'query' in request.GET or 'meta' in request.GET or\
        'token' in request.GET


def value_for_type(form, field, value):
    if form._meta.get_field(field).get_internal_type() == 'BooleanField':
        return str2bool(value)

    return value


def external_export_response(export):
    if isinstance(export, Export) \
            and export.internal_status == Export.SUCCESSFUL:
        return HttpResponseRedirect(export.export_url)
    else:
        http_status = status.HTTP_400_BAD_REQUEST

    return Response(json.dumps(export), http_status,
                    content_type="application/json")


def log_export(request, xform, export_type):
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


def custom_response_handler(request, xform, query, export_type,
                            token=None, meta=None):
    export_type = _get_export_type(export_type)

    if export_type in external_export_types and \
            (token is not None) or (meta is not None):
        export_type = Export.EXTERNAL_EXPORT

    # check if we need to re-generate,
    # we always re-generate if a filter is specified
    if should_regenerate_export(xform, export_type, request):
        export = _generate_new_export(request, xform, query, export_type)
    else:
        export = newset_export_for(xform, export_type)
        if not export.filename:
            # tends to happen when using newset_export_for.
            export = _generate_new_export(request, xform, query, export_type)

    log_export(request, xform, export_type)

    if export_type == Export.EXTERNAL_EXPORT:
        return external_export_response(export)

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    path, ext = os.path.splitext(export.filename)
    ext = ext[1:]
    id_string = None if request.GET.get('raw') else xform.id_string
    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[ext], id_string, extension=ext,
        file_path=export.filepath)

    return response


def _try_update_xlsform(request, xform, owner):
    survey = \
        utils.publish_xlsform(request, owner, xform.id_string, xform.project)

    if isinstance(survey, XForm):
        serializer = XFormSerializer(
            xform, context={'request': request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(survey, status=status.HTTP_400_BAD_REQUEST)


class XFormViewSet(AnonymousUserPublicFormsMixin,
                   LabelsMixin,
                   LastModifiedMixin,
                   ModelViewSet):

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
- `drop_xls_url`: the drop box url to an xlsform
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
>
> OR post an xlsform via Dropbox url
>
>       curl -X POST -d \
"dropbox_xls_url=https://www.dropbox.com/s/ynenld7xdf1vdlo/tutorial.xls?dl=1" \
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
If you are using `PUT`, you have to provide the `uuid, description,
downloadable, owner, public, public_data, title` fields. \n
 With `PATCH` you only need to provide at least one of the fields.

- `xls_file`: Can only be updated when there are no submissions.

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

## Export form data asynchronously

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/export_async
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058/export_async?format=xls
>
> Response
>
>       HTTP 202 Accepted
>       {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}
>
> You can use the `job_uuid` value to check the progress of data export

## Check progress of exporting form data asynchronously

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/export_async?job_uuid=UUID
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058/export_async?job_uuid=\
d1559e9e-5bab-480d-9804-e32111e8b2b8
>
> Response
> If the job is done:-
>
>       HTTP 202 Accepted
>       {
>           "job_status": "SUCCESS",
>           "export_url": "https://ona.io/api/v1/forms/28058.xls"
>       }
>

## Delete an XLS form asynchronously

<pre class="prettyprint">
<b>POST</b> /api/v1/forms/<code>{pk}</code>/delete_async
</pre>
> Example
>
>       curl -X DELETE https://ona.io/api/v1/forms/28058/delete_async
>
> Response
>
>       HTTP 202 Accepted
>       {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}
>
> You can use the `job_uuid` value to check on the upload progress (see below)

## Check on XLS form deletion progress

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/delete_async?job_uuid=UUID
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058/delete_async?job_uuid=\
d1559e9e-5bab-480d-9804-e32111e8b2b8
>
> Response
> If the job is done:-
>
>       HTTP 202 Accepted
>       {"JOB_STATUS": "SUCCESS"}

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
>       {"enketo_url": "https://h6ic6.enketo.org/webform",
>        "enketo_preview_url": "https://H6Ic6.enketo.org/webform"}
>
>        HTTP 200 OK

## Get form data in xls, csv format.

Get form data exported as xls, csv, csv zip, sav zip format.

Where:

- `pk` - is the form unique identifier
- `format` - is the data export format i.e csv, xls, csvzip, savzip

Params for the custom xls report

- `meta`  - the metadata id containing the template url
-  `token`  - the template url
-  `data_id`  - the unique id of the submission

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/{pk}.{format}</code>
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/28058.xls

> Binary file export of the format specified is returned as the response for
>the download.
>
> Response
>
>        HTTP 200 OK

> Example 2 Custom XLS reports (beta)
>
>       curl -X GET https://ona.io/api/v1/forms/28058.xls?meta=12121
>                   or
>       curl -X GET https://ona.io/api/v1/forms/28058.xls?token={url}
>
> XLS file is downloaded
>
> Response
>
>        HTTP 200 OK

> Example 3 Custom XLS reports with meta or token and data_id(beta)
<pre class="prettyprint">
<b>GET</b> /api/v1/forms/{pk}.{format}?{meta}&{data_id} -L -o {filename.xls}
</code>
</pre>
>
>       curl "https://ona.io/api/v1/forms/2.xls?meta=19&data_id=7" -L -o \
data.xlsx
>                   or
>       curl "https://ona.io/api/v1/forms/2.xls?token={url}&data_id=7" -L \
-o data.xlsx
>
> XLS file is downloaded
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

You can clone a form to a specific user account using `POST` with

- `username` of the user you want to clone the form to

<pre class="prettyprint">
<b>POST</b> /api/v1/forms/<code>{pk}</code>/clone
</pre>

> Example
>
>       curl -X POST https://ona.io/api/v1/forms/123/clone \
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

## Import CSV data to existing form
- `csv_file` a valid csv file with exported \
data (instance/submission per row)
<pre class="prettyprint">
<b>POST</b> /api/v1/forms/<code>{pk}</code>/csv_import
</pre>
> Example
>
>       curl -X POST https://ona.io/api/v1/forms/123/csv_import \
-F csv_file=@/path/to/csv_import.csv
>
> Response
> If the job was executed immediately:-
>
>       HTTP 200 OK
>       {
>           "additions": 9,
>           "updates": 0
>       }
>
> If the import is a long running task:-
>
>       HTTP 200 OK
>       {"job_uuid": "04874cee-5fea-4552-a6c1-3c182b8b511f"}
>
> You can use the `job_uuid value to check on the import progress (see below)
## Check on CSV data import progress
- `job_uuid` a valid csv import job_uuid returned by a long running import \
previous call
<pre class="prettyprint">
<b>GET</b> /api/v1/forms/<code>{pk}</code>/csv_import?job_uuid=UUID
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/123/csv_import?job_uuid=UUID
>
> Response
> If the job is done:-
>
>       HTTP 200 OK
>       {
>           "additions": 90000,
>           "updates": 10000
>       }
>
> If the import is still running:-
>
>       HTTP 200 OK
>       {
>           "current": 100,
>           "total": 100000
>       }
## Upload a XLS form async

<pre class="prettyprint">
<b>POST</b> /api/v1/forms/create_async
</pre>
> Example
>
>       curl -X POST https://ona.io/api/v1/forms/create_async \
-F xls_file=@/path/to/xls_file
>
> Response
>
>       HTTP 202 Accepted
>       {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}
>
> You can use the `job_uuid value to check on the upload progress (see below)
## Check on XLS form upload progress

<pre class="prettyprint">
<b>GET</b> /api/v1/forms/create_async/?job_uuid=UUID
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/forms/create_async?job_uuid=UUID
>
> Response
> If the job is done:-
>
>       HTTP 201 Created
>      {
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
>
> If the upload is still running:-
>
>       HTTP 202 Accepted
>       {
>           "JOB_STATUS": "PENDING"
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
    queryset = XForm.objects.select_related()
    serializer_class = XFormSerializer
    lookup_field = 'pk'
    extra_lookup_fields = None
    permission_classes = [XFormPermissions, ]
    updatable_fields = set(('description', 'downloadable', 'require_auth',
                            'shared', 'shared_data', 'title'))
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.TagFilter,
                       filters.XFormOwnerFilter)

    public_forms_endpoint = 'public'

    def create(self, request, *args, **kwargs):
        try:
            owner = _get_owner(request)
        except ValidationError as e:
            return Response({'message': e.messages[0]},
                            status=status.HTTP_400_BAD_REQUEST)

        survey = utils.publish_xlsform(request, owner)
        if isinstance(survey, XForm):
            xform = XForm.objects.get(pk=survey.pk)
            serializer = XFormSerializer(
                xform, context={'request': request})
            headers = self.get_success_headers(serializer.data)

            return Response(serializer.data, status=status.HTTP_201_CREATED,
                            headers=headers)

        return Response(survey, status=status.HTTP_400_BAD_REQUEST)

    @list_route(methods=['POST', 'GET'])
    def create_async(self, request, *args, **kwargs):
        """ Temporary Endpoint for Async form creation """
        resp = headers = {}
        resp_code = status.HTTP_400_BAD_REQUEST

        if request.method == 'GET':
            survey = tasks.get_async_status(
                request.QUERY_PARAMS.get('job_uuid'))

            if 'pk' in survey:
                xform = XForm.objects.get(pk=survey.get('pk'))
                serializer = XFormSerializer(
                    xform, context={'request': request})
                headers = self.get_success_headers(serializer.data)
                resp = serializer.data
                resp_code = status.HTTP_201_CREATED
            else:
                resp_code = status.HTTP_202_ACCEPTED
                resp.update(survey)
        else:
            try:
                owner = _get_owner(request)
            except ValidationError as e:
                return Response({'message': e.messages[0]},
                                status=status.HTTP_400_BAD_REQUEST)

            fname = request.FILES.get('xls_file').name
            resp.update(
                {u'job_uuid':
                 tasks.publish_xlsform_async.delay(
                     request.user, request.POST, owner,
                     ({'name': fname,
                       'data': request.FILES.get('xls_file').read()}
                      if isinstance(request.FILES.get('xls_file'),
                                    InMemoryUploadedFile) else
                      {'name': fname,
                       'path': request.FILES.get(
                           'xls_file').temporary_file_path()})).task_id})
            resp_code = status.HTTP_202_ACCEPTED

        return Response(data=resp, status=resp_code, headers=headers)

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
            preview_url = get_enketo_preview_url(request,
                                                 request.user.username,
                                                 self.object.id_string)
        except EnketoError:
            pass
        else:
            if url and preview_url:
                http_status = status.HTTP_200_OK
                data = {"enketo_url": url, "enketo_preview_url": preview_url}

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
        export_type = kwargs.get('format')
        query = request.GET.get("query", {})
        token = request.GET.get('token')
        meta = request.GET.get('meta')

        if export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(XFormViewSet, self).retrieve(request, *args, **kwargs)
        if not xform.xls:
            raise Http404(_("xls file does not exist"))

        return custom_response_handler(request,
                                       xform,
                                       query,
                                       export_type,
                                       token,
                                       meta)

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

    @action(methods=['POST'])
    def clone(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = {'xform': self.object.pk,
                'username': request.DATA.get('username')}
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

    @detail_route(methods=['POST', 'GET'])
    def csv_import(self, request, *args, **kwargs):
        """ Endpoint for CSV data imports
        Calls :py:func:`onadata.libs.utils.csv_import.submit_csv` for POST
        requests passing the `request.FILES.get('csv_file')` upload
        for import and
        :py:func:onadata.libs.utils.csv_import.get_async_csv_submission_status
        for GET requests passing `job_uuid` query param for job progress
        polling
        """
        self.object = self.get_object()
        resp = {}
        if request.method == 'GET':
            resp.update(get_async_csv_submission_status(
                request.QUERY_PARAMS.get('job_uuid')))
            self.last_modified_date = timezone.now()
        else:
            csv_file = request.FILES.get('csv_file', None)
            if csv_file is None:
                resp.update({u'error': u'csv_file field empty'})
            else:
                num_rows = sum(1 for row in csv_file) - 1
                if num_rows < settings.CSV_ROW_IMPORT_ASYNC_THRESHOLD:
                    resp.update(submit_csv(request.user.username,
                                           self.object, csv_file))
                else:
                    resp.update(
                        {u'task_id': submit_csv_async.delay(
                            request.user.username, self.object,
                            csv_file).task_id})

        return Response(
            data=resp,
            status=status.HTTP_200_OK if resp.get('error') is None else
            status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        self.object = self.get_object()
        owner = self.object.user

        # updating the file
        if request.FILES:
            return _try_update_xlsform(request, self.object, owner)

        return super(XFormViewSet, self).partial_update(request, *args,
                                                        **kwargs)

    @action(methods=['DELETE', 'GET'])
    def delete_async(self, request, *args, **kwargs):
        if request.method == 'DELETE':
            time_async_triggered = datetime.now()
            self.object = self.get_object()
            self.object.deleted_at = time_async_triggered
            self.object.save()
            xform = self.object
            resp = {
                u'job_uuid': tasks.delete_xform_async.delay(xform).task_id,
                u'time_async_triggered': time_async_triggered}
            resp_code = status.HTTP_202_ACCEPTED

        elif request.method == 'GET':
            job_uuid = request.QUERY_PARAMS.get('job_uuid')
            resp = tasks.get_async_status(job_uuid)
            resp_code = status.HTTP_202_ACCEPTED
        return Response(data=resp, status=resp_code)

    @action(methods=['GET'])
    def export_async(self, request, *args, **kwargs):
        job_uuid = request.QUERY_PARAMS.get('job_uuid')
        export_type = request.QUERY_PARAMS.get('format')
        query = request.GET.get("query", {})
        xform = self.get_object()

        if job_uuid:
            job = AsyncResult(job_uuid)

            if job.state == 'SUCCESS':
                export_id = job.result
                export = Export.objects.get(id=export_id)
                if export:
                    export_url = reverse(
                        'xform-detail',
                        kwargs={'pk': xform.pk, 'format': export.export_type},
                        request=request
                    )
                    resp = {
                        u'job_status': job.state,
                        u'export_url': export_url
                    }
                else:
                    raise Http404(_("Export Fot Found"))

            else:
                resp = {
                    'JOB_STATUS': job.state
                }

        else:
            export, async_result = viewer_task.create_async_export(
                xform, export_type, query, False)
            resp = {
                u'job_uuid': async_result.task_id
            }
            resp = json.dumps(resp)
        resp_code = status.HTTP_202_ACCEPTED
        return Response(data=resp,
                        status=resp_code,
                        content_type="application/json")
