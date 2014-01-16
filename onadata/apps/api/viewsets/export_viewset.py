import os
import json

from datetime import datetime
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name

from rest_framework import permissions
from rest_framework import exceptions
from rest_framework.renderers import BaseRenderer
from rest_framework.settings import api_settings
from rest_framework.viewsets import ReadOnlyModelViewSet

from onadata.apps.api import mixins, serializers
from onadata.apps.odk_logger.models import XForm
from onadata.apps.odk_viewer.models import Export
from onadata.apps.odk_viewer.pandas_mongo_bridge import NoRecordsFoundError
from onadata.libs.utils.export_tools import generate_export,\
    should_create_new_export
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils import log
from onadata.libs.utils.export_tools import newset_export_for


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


class ExportViewSet(mixins.MultiLookupMixin, ReadOnlyModelViewSet):
    """
Export data in xls, csv format.

Where:

- `owner` - is the organization or user to which the form(s) belong to.
- `pk` - is the project id
- `formid` - is the form id
- `format` - is the data export format i.e csv or xls

## Get Form Information

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
        SAVZIPRenderer
    ]
    queryset = XForm.objects.filter()
    serializer_class = serializers.XFormSerializer
    lookup_fields = ('owner', 'pk')
    lookup_field = 'owner'
    extra_lookup_fields = None
    permission_classes = [permissions.DjangoModelPermissions, ]

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

    def list(self, request, *args, **kwargs):
        return super(ExportViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        xform = self.get_object()
        query = request.GET.get("query")
        export_type = kwargs.get('format', 'xls')
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
