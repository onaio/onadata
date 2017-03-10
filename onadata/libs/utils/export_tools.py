import hashlib
import json
import math
import os
import re
import time
from datetime import datetime
from urlparse import urlparse

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import File
from django.core.files.storage import get_storage_class
from django.core.files.temp import NamedTemporaryFile
from django.db import OperationalError
from django.db.models.query import QuerySet
from django.shortcuts import render_to_response
from json2xlsclient.client import Client
from savReaderWriter import SPSSIOError

from onadata.apps.logger.models import Attachment, Instance, OsmData, XForm
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.viewer.models.export import (Export,
                                               get_export_options_query_kwargs)
from onadata.apps.viewer.models.parsed_instance import query_data
from onadata.libs.exceptions import J2XException, NoRecordsFoundError
from onadata.libs.utils.common_tags import (DATAVIEW_EXPORT,
                                            GROUPNAME_REMOVED_FLAG)
from onadata.libs.utils.common_tools import str_to_bool
from onadata.libs.utils.export_builder import ExportBuilder
from onadata.libs.utils.model_tools import (get_columns_with_hxl,
                                            queryset_iterator)
from onadata.libs.utils.osm import get_combined_osm
from onadata.libs.utils.viewer_tools import (create_attachments_zipfile,
                                             image_urls)

DEFAULT_GROUP_DELIMITER = '/'
EXPORT_QUERY_KEY = 'query'
MAX_RETRIES = 3


def export_retry(tries, delay=3, backoff=2):
    '''
    Adapted from code found here:
        http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    Retries a function or method until it returns True.

    *delay* sets the initial delay in seconds, and *backoff* sets the
    factor by which the delay should lengthen after each failure.
    *backoff* must be greater than 1, or else it isn't really a backoff.
    *tries* must be at least 0, and *delay* greater than 0.
    '''

    if backoff <= 1:  # pragma: no cover
        raise ValueError("backoff must be greater than 1")

    tries = math.floor(tries)
    if tries < 0:  # pragma: no cover
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:  # pragma: no cover
        raise ValueError("delay must be greater than 0")

    def decorator_retry(func):
        def function_retry(self, *args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 0:
                try:
                    result = func(self, *args, **kwargs)
                except OperationalError:
                    mtries -= 1
                    time.sleep(mdelay)
                    mdelay *= backoff
                else:
                    return result
            # Last ditch effort run against master database
            if len(getattr(settings, 'SLAVE_DATABASES', [])):
                from multidb.pinning import use_master
                with use_master:
                    return func(self, *args, **kwargs)

            # last attempt, exception raised from function is propagated
            return func(self, *args, **kwargs)

        return function_retry
    return decorator_retry


def dict_to_flat_export(d, parent_index=0):
    pass


def md5hash(string):
    return hashlib.md5(string).hexdigest()


def get_export_options(options):
    export_options = {
        key: value for key, value in options.iteritems()
        if key in Export.EXPORT_OPTION_FIELDS}

    if EXPORT_QUERY_KEY in export_options:
        query_str = '{}'.format(export_options[EXPORT_QUERY_KEY])

        export_options[EXPORT_QUERY_KEY] = md5hash(query_str)

    return export_options


def get_or_create_export(export_id, xform, export_type, options):
    if export_id:
        try:
            return Export.objects.get(id=export_id)
        except Export.DoesNotExist:
            pass

    return create_export_object(xform, export_type, options)


@export_retry(MAX_RETRIES)
def generate_export(export_type, xform, export_id=None, options=None,
                    retries=0):
    """
    Create appropriate export object given the export type.

    param: export_type
    param: xform
    params: export_id: ID of export object associated with the request
    param: options: additional parameters required for the lookup.
        binary_select_multiples: boolean flag
        end: end offset
        ext: export extension type
        dataview_pk: dataview pk
        group_delimiter: "/" or "."
        query: filter_query for custom queries
        remove_group_name: boolean flag
        split_select_multiples: boolean flag
    """
    username = xform.user.username
    id_string = xform.id_string
    end = options.get("end")
    extension = options.get("extension", export_type)
    filter_query = options.get("query")
    remove_group_name = options.get("remove_group_name", False)
    start = options.get("start")

    export_type_func_map = {
        Export.XLS_EXPORT: 'to_xls_export',
        Export.CSV_EXPORT: 'to_flat_csv_export',
        Export.CSV_ZIP_EXPORT: 'to_zipped_csv',
        Export.SAV_ZIP_EXPORT: 'to_zipped_sav',
        Export.GOOGLE_SHEETS_EXPORT: 'to_google_sheets',
    }

    if xform is None:
        xform = XForm.objects.get(
            user__username__iexact=username, id_string__iexact=id_string)

    dataview = None
    if options.get("dataview_pk"):
        dataview = DataView.objects.get(pk=options.get("dataview_pk"))
        records = dataview.query_data(dataview, all_data=True)
    else:
        records = query_data(xform, query=filter_query, start=start, end=end)

    if isinstance(records, QuerySet):
        records = records.iterator()

    export_builder = ExportBuilder()

    export_builder.TRUNCATE_GROUP_TITLE = True \
        if export_type == Export.SAV_ZIP_EXPORT else remove_group_name
    export_builder.GROUP_DELIMITER = options.get(
        "group_delimiter", DEFAULT_GROUP_DELIMITER
    )
    export_builder.SPLIT_SELECT_MULTIPLES = options.get(
        "split_select_multiples", True
    )
    export_builder.BINARY_SELECT_MULTIPLES = options.get(
        "binary_select_multiples", False
    )
    export_builder.INCLUDE_LABELS = options.get('include_labels', False)
    export_builder.INCLUDE_LABELS_ONLY = options.get(
        'include_labels_only', False
    )
    export_builder.INCLUDE_HXL = options.get('include_hxl', False)

    export_builder.INCLUDE_IMAGES \
        = options.get("include_images", settings.EXPORT_WITH_IMAGE_DEFAULT)

    # 'win_excel_utf8' is only relevant for CSV exports
    if 'win_excel_utf8' in options and export_type != Export.CSV_EXPORT:
        del options['win_excel_utf8']

    export_builder.set_survey(xform.survey)

    temp_file = NamedTemporaryFile(suffix=("." + extension))

    columns_with_hxl = export_builder.INCLUDE_HXL and get_columns_with_hxl(
        xform.survey_elements)

    # get the export function by export type
    func = getattr(export_builder, export_type_func_map[export_type])
    try:
        func.__call__(
            temp_file.name, records, username, id_string, filter_query,
            start=start, end=end, dataview=dataview, xform=xform,
            options=options, columns_with_hxl=columns_with_hxl
        )
    except NoRecordsFoundError:
        pass
    except SPSSIOError as e:
        export = get_or_create_export(export_id, xform, export_type, options)
        export.error_message = str(e)
        export.internal_status = Export.FAILED
        export.save()

        return export

    # generate filename
    basename = "%s_%s" % (
        id_string, datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f"))

    if remove_group_name:
        # add 'remove group name' flag to filename
        basename = "{}-{}".format(basename, GROUPNAME_REMOVED_FLAG)
    if dataview:
        basename = "{}-{}".format(basename, DATAVIEW_EXPORT)

    filename = basename + "." + extension

    # check filename is unique
    while not Export.is_filename_unique(xform, filename):
        filename = increment_index_in_filename(filename)

    file_path = os.path.join(
        username,
        'exports',
        id_string,
        export_type,
        filename)

    # TODO: if s3 storage, make private - how will we protect local storage??
    storage = get_storage_class()()
    # seek to the beginning as required by storage classes
    temp_file.seek(0)
    export_filename = storage.save(file_path, File(temp_file, file_path))
    temp_file.close()

    dir_name, basename = os.path.split(export_filename)

    # get or create export object
    export = get_or_create_export(export_id, xform, export_type, options)

    export.filedir = dir_name
    export.filename = basename
    export.internal_status = Export.SUCCESSFUL
    # do not persist exports that have a filter
    # Get URL of the exported sheet.
    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        export.export_url = export_builder.url

    # if we should create a new export is true, we should not save it
    if start is None and end is None:
        export.save()
    return export


def create_export_object(xform, export_type, options):
    export_options = get_export_options(options)
    return Export(xform=xform, export_type=export_type, options=export_options)


def should_create_new_export(xform,
                             export_type,
                             options,
                             request=None):
    """
    Function that determines whether to create a new export.
    param: xform
    param: export_type
    param: options: additional parameters required for the lookup.
        remove_group_name: boolean flag
        group_delimiter: "/" or "." with "/" as the default
        split_select_multiples: boolean flag
        binary_select_multiples: boolean flag
    params: request: Get params are used to determine if new export is required
    """
    split_select_multiples = options.get('split_select_multiples', True)

    if getattr(settings, 'SHOULD_ALWAYS_CREATE_NEW_EXPORT', False):
        return True

    if (request and (frozenset(request.GET.keys()) &
                     frozenset(['start', 'end', 'data_id']))) or\
            not split_select_multiples:
        return True

    export_options_kwargs = get_export_options_query_kwargs(options)
    export_query = Export.objects.filter(
        xform=xform,
        export_type=export_type,
        **export_options_kwargs
    )

    if export_query.count() == 0 or\
       Export.exports_outdated(xform, export_type, options=options):
        return True

    return False


def newest_export_for(xform, export_type, options):
    """
    Retrieve the latest export given the following arguments:

    param: xform
    param: export_type
    param: options: additional parameters required for the lookup.
        remove_group_name: boolean flag
        group_delimiter: "/" or "." with "/" as the default
        split_select_multiples: boolean flag
        binary_select_multiples: boolean flag
    """

    export_options_kwargs = get_export_options_query_kwargs(options)
    export_query = Export.objects.filter(
        xform=xform,
        export_type=export_type,
        **export_options_kwargs
    )

    return export_query.latest('created_on')


def increment_index_in_filename(filename):
    """
    filename should be in the form file.ext or file-2.ext - we check for the
    dash and index and increment appropriately
    """
    # check for an index i.e. dash then number then dot extension
    regex = re.compile(r"(.+?)\-(\d+)(\..+)")
    match = regex.match(filename)
    if match:
        basename = match.groups()[0]
        index = int(match.groups()[1]) + 1
        ext = match.groups()[2]
    else:
        index = 1
        # split filename from ext
        basename, ext = os.path.splitext(filename)
    new_filename = "%s-%d%s" % (basename, index, ext)
    return new_filename


def generate_attachments_zip_export(export_type, username, id_string,
                                    export_id=None, options=None,
                                    xform=None):
    """
    Generates zip export of attachments.

    param: export_type
    params: username: logged in username
    params: id_string: xform id_string
    params: export_id: ID of export object associated with the request
    param: options: additional parameters required for the lookup.
        ext: File extension of the generated export
    """
    extension = options.get("extension", export_type)

    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)

    if options.get("dataview_pk"):
        dataview = DataView.objects.get(pk=options.get("dataview_pk"))
        records = dataview.query_data(dataview, all_data=True)
        instances_ids = [rec.get('_id') for rec in records]
        attachments = Attachment.objects.filter(instance_id__in=instances_ids)
    else:
        attachments = Attachment.objects.filter(instance__xform=xform)

    basename = "%s_%s" % (id_string,
                          datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    filename = basename + "." + extension
    file_path = os.path.join(
        username,
        'exports',
        id_string,
        export_type,
        filename)
    storage = get_storage_class()()
    zip_file = None

    try:
        zip_file = create_attachments_zipfile(attachments)

        try:
            temp_file = open(zip_file.name)
            export_filename = storage.save(
                file_path,
                File(temp_file, file_path))
        finally:
            temp_file.close()
    finally:
        zip_file and zip_file.close()

    dir_name, basename = os.path.split(export_filename)

    # get or create export object
    if(export_id):
        export = Export.objects.get(id=export_id)
    else:
        export_options = get_export_options(options)
        export = Export.objects.create(xform=xform,
                                       export_type=export_type,
                                       options=export_options)

    export.filedir = dir_name
    export.filename = basename
    export.internal_status = Export.SUCCESSFUL
    export.save()
    return export


def generate_kml_export(export_type, username, id_string, export_id=None,
                        options=None, xform=None):
    """
    Generates kml export for geographical data

    param: export_type
    params: username: logged in username
    params: id_string: xform id_string
    params: export_id: ID of export object associated with the request
    param: options: additional parameters required for the lookup.
        ext: File extension of the generated export
    """
    extension = options.get("extension", export_type)

    user = User.objects.get(username=username)
    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)
    response = render_to_response(
        'survey.kml', {'data': kml_export_data(id_string, user, xform=xform)})

    basename = "%s_%s" % (id_string,
                          datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    filename = basename + "." + extension
    file_path = os.path.join(
        username,
        'exports',
        id_string,
        export_type,
        filename)

    storage = get_storage_class()()
    temp_file = NamedTemporaryFile(suffix=extension)
    temp_file.write(response.content)
    temp_file.seek(0)
    export_filename = storage.save(
        file_path,
        File(temp_file, file_path))
    temp_file.close()

    dir_name, basename = os.path.split(export_filename)

    # get or create export object
    if export_id and Export.objects.filter(pk=export_id).exists():
        export = Export.objects.get(id=export_id)
    else:
        export_options = get_export_options(options)
        export = Export.objects.create(xform=xform,
                                       export_type=export_type,
                                       options=export_options)

    export.filedir = dir_name
    export.filename = basename
    export.internal_status = Export.SUCCESSFUL
    export.save()

    return export


def kml_export_data(id_string, user, xform=None):
    if xform is None:
        xform = XForm.objects.get(id_string=id_string, user=user)

    instances = Instance.objects.filter(
        xform__user=user, xform__id_string=id_string, geom__isnull=False
    ).order_by('id')
    data_for_template = []

    labels = {}

    def cached_get_labels(xpath):
        if xpath in labels.keys():
            return labels[xpath]
        labels[xpath] = xform.get_label(xpath)
        return labels[xpath]

    for instance in queryset_iterator(instances):
        # read the survey instances
        data_for_display = instance.get_dict()
        xpaths = data_for_display.keys()
        xpaths.sort(cmp=instance.xform.get_xpath_cmp())
        label_value_pairs = [
            (cached_get_labels(xpath), data_for_display[xpath]) for xpath in
            xpaths if not xpath.startswith(u"_")]
        table_rows = ['<tr><td>%s</td><td>%s</td></tr>' % (k, v) for k, v
                      in label_value_pairs]
        img_urls = image_urls(instance)
        img_url = img_urls[0] if img_urls else ""
        point = instance.point

        if point:
            data_for_template.append({
                'name': id_string,
                'id': instance.id,
                'lat': point.y,
                'lng': point.x,
                'image_urls': img_urls,
                'table': '<table border="1"><a href="#"><img width="210" '
                         'class="thumbnail" src="%s" alt=""></a>%s'
                         '</table>' % (img_url, ''.join(table_rows))})

    return data_for_template


def generate_osm_export(export_type, username, id_string, export_id=None,
                        options=None, xform=None):
    """
    Generates osm export for OpenStreetMap data

    param: export_type
    params: username: logged in username
    params: id_string: xform id_string
    params: export_id: ID of export object associated with the request
    param: options: additional parameters required for the lookup.
        ext: File extension of the generated export
    """

    extension = options.get("extension", export_type)

    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)
    osm_list = OsmData.objects.filter(instance__xform=xform)
    content = get_combined_osm(osm_list)

    basename = "%s_%s" % (id_string,
                          datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    filename = basename + "." + extension
    file_path = os.path.join(
        username,
        'exports',
        id_string,
        export_type,
        filename)

    storage = get_storage_class()()
    temp_file = NamedTemporaryFile(suffix=extension)
    temp_file.write(content)
    temp_file.seek(0)
    export_filename = storage.save(
        file_path,
        File(temp_file, file_path))
    temp_file.close()

    dir_name, basename = os.path.split(export_filename)

    # get or create export object
    if export_id and Export.objects.filter(pk=export_id).exists():
        export = Export.objects.get(id=export_id)
    else:
        export_options = get_export_options(options)
        export = Export.objects.create(xform=xform,
                                       export_type=export_type,
                                       options=export_options)

    export.filedir = dir_name
    export.filename = basename
    export.internal_status = Export.SUCCESSFUL
    export.save()

    return export


def _get_records(instances):
    return [clean_keys_of_slashes(instance)
            for instance in instances]


def clean_keys_of_slashes(record):
    """
    Replaces the slashes found in a dataset keys with underscores
    :param record: list containing a couple of dictionaries
    :return: record with keys without slashes
    """
    for key in record.keys():
        value = record[key]
        if '/' in key:
            # replace with _
            record[key.replace('/', '_')]\
                = record.pop(key)
        # Check if the value is a list containing nested dict and apply same
        if value:
            if isinstance(value, list) and isinstance(value[0], dict):
                for v in value:
                    clean_keys_of_slashes(v)

    return record


def _get_server_from_metadata(xform, meta, token):
    report_templates = MetaData.external_export(xform)

    if meta:
        try:
            int(meta)
        except ValueError:
            raise Exception(u"Invalid metadata pk {0}".format(meta))

        # Get the external server from the metadata
        result = report_templates.get(pk=meta)
        server = result.external_export_url
        name = result.external_export_name
    elif token:
        server = token
        name = None
    else:
        # Take the latest value in the metadata
        if not report_templates:
            raise Exception(
                u"Could not find the template token: Please upload template.")

        server = report_templates[0].external_export_url
        name = report_templates[0].external_export_name

    return server, name


def generate_external_export(export_type, username, id_string, export_id=None,
                             options=None, xform=None):
    """
    Generates external export using ONA data through an external service.

    param: export_type
    params: username: logged in username
    params: id_string: xform id_string
    params: export_id: ID of export object associated with the request
    param: options: additional parameters required for the lookup.
        data_id: instance id
        query: filter_query for custom queries
        meta: metadata associated with external export
        token: authentication key required by external service
    """
    data_id = options.get("data_id")
    filter_query = options.get("query")
    meta = options.get("meta")
    token = options.get("token")

    if xform is None:
        xform = XForm.objects.get(
            user__username__iexact=username, id_string__iexact=id_string)
    user = User.objects.get(username=username)

    server, name = _get_server_from_metadata(xform, meta, token)

    # dissect the url
    parsed_url = urlparse(server)

    token = parsed_url.path[5:]

    ser = parsed_url.scheme + '://' + parsed_url.netloc

    # Get single submission data
    if data_id:
        inst = Instance.objects.filter(xform__user=user,
                                       xform__id_string=id_string,
                                       deleted_at=None,
                                       pk=data_id)

        instances = [inst[0].json if inst else {}]
    else:
        instances = query_data(xform, query=filter_query)

    records = _get_records(instances)

    status_code = 0

    if records and server:
        try:
            client = Client(ser)
            response = client.xls.create(token, json.dumps(records))

            if hasattr(client.xls.conn, 'last_response'):
                status_code = client.xls.conn.last_response.status_code
        except Exception as e:
            raise J2XException(
                u"J2X client could not generate report. Server -> {0},"
                u" Error-> {1}".format(server, e)
            )
    else:
        if not server:
            raise J2XException(u"External server not set")
        elif not records:
            raise J2XException(
                u"No record to export. Form -> {0}".format(id_string)
            )

    # get or create export object
    if export_id:
        export = Export.objects.get(id=export_id)
    else:
        export_options = get_export_options(options)
        export = Export.objects.create(xform=xform,
                                       export_type=export_type,
                                       options=export_options)

    export.export_url = response
    if status_code == 201:
        export.internal_status = Export.SUCCESSFUL
        export.filename = name + '-' + response[5:] if name else response[5:]
        export.export_url = ser + response
    else:
        export.internal_status = Export.FAILED

    export.save()

    return export


def upload_template_for_external_export(server, file_obj):

    try:
        client = Client(server)
        response = client.template.create(template_file=file_obj)

        if hasattr(client.template.conn, 'last_response'):
            status_code = client.template.conn.last_response.status_code
    except Exception as e:
        response = str(e)
        status_code = 500

    return str(status_code) + '|' + response


def parse_request_export_options(params):
    """
    Parse export options in the request object into values returned in a
    list. The list represents a boolean for whether the group name should be
    removed, the group delimiter, and a boolean for whether select multiples
    should be split.
    """
    boolean_list = ['true', 'false']
    options = {}
    remove_group_name = params.get('remove_group_name') and \
        params.get('remove_group_name').lower()
    do_not_split_select_multiples = params.get(
        'do_not_split_select_multiples')
    include_labels = params.get('include_labels', False)
    include_labels_only = params.get('include_labels_only', False)
    include_hxl = params.get('include_hxl', True)

    if include_labels is not None:
        options['include_labels'] = str_to_bool(include_labels)

    if include_labels_only is not None:
        options['include_labels_only'] = str_to_bool(include_labels_only)

    if include_hxl is not None:
        options['include_hxl'] = str_to_bool(include_hxl)

    if remove_group_name in boolean_list:
        options["remove_group_name"] = str_to_bool(remove_group_name)
    else:
        options["remove_group_name"] = False

    if params.get("group_delimiter") in ['.', DEFAULT_GROUP_DELIMITER]:
        options['group_delimiter'] = params.get("group_delimiter")
    else:
        options['group_delimiter'] = DEFAULT_GROUP_DELIMITER

    options['split_select_multiples'] = \
        not str_to_bool(do_not_split_select_multiples)

    if 'include_images' in params:
        options["include_images"] = str_to_bool(
            params.get("include_images"))
    else:
        options["include_images"] = settings.EXPORT_WITH_IMAGE_DEFAULT

    options['win_excel_utf8'] = str_to_bool(params.get('win_excel_utf8'))

    return options
