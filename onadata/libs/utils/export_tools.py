# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
Export tools
"""

from __future__ import unicode_literals

import hashlib
import importlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Iterator

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

import six
from json2xlsclient.client import Client
from multidb.pinning import use_master
from rest_framework import exceptions
from six import iteritems
from six.moves.urllib.parse import urlparse

try:
    from savReaderWriter import SPSSIOError
except ImportError:
    SPSSIOError = Exception

from onadata.apps.logger.models import (
    Attachment,
    Entity,
    EntityList,
    Instance,
    OsmData,
    XForm,
)
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.viewer.models.export import (
    Export,
    GenericExport,
    get_export_options_query_kwargs,
)
from onadata.apps.viewer.models.parsed_instance import (
    query_count,
    query_data,
    query_fields_data,
)
from onadata.libs.exceptions import J2XException, NoRecordsFoundError
from onadata.libs.serializers.geojson_serializer import GeoJsonSerializer
from onadata.libs.utils.common_tags import (
    DATAVIEW_EXPORT,
    GEOJSON_EXTRA_DATA_EXPORT_OPTION_MAP,
    GROUPNAME_REMOVED_FLAG,
)
from onadata.libs.utils.common_tools import (
    cmp_to_key,
    report_exception,
    retry,
    str_to_bool,
)
from onadata.libs.utils.export_builder import ExportBuilder
from onadata.libs.utils.model_tools import get_columns_with_hxl, queryset_iterator
from onadata.libs.utils.osm import get_combined_osm
from onadata.libs.utils.viewer_tools import create_attachments_zipfile, image_urls

DEFAULT_GROUP_DELIMITER = "/"
DEFAULT_INDEX_TAGS = ("[", "]")
SUPPORTED_INDEX_TAGS = ("[", "]", "(", ")", "{", "}", ".", "_")
EXPORT_QUERY_KEY = "query"
MAX_RETRIES = 3

User = get_user_model()


def md5hash(string):
    """
    Return the MD5 hex digest of the given string.
    """
    return hashlib.md5(string).hexdigest()


def get_export_options(options):
    """
    Returns expirt options as defined in Export.EXPORT_OPTION_FIELDS from a
    list of provided options to be saved with each Export object.
    """
    export_options = {
        key: value
        for (key, value) in iteritems(options)
        if key in Export.EXPORT_OPTION_FIELDS
    }

    return export_options


def get_or_create_export(export_id, xform, export_type, options):
    """
    Returns an existing export object or creates a new one with the given
    options.
    """
    if export_id:
        try:
            return Export.objects.get(pk=export_id)
        except Export.DoesNotExist:
            if getattr(settings, "SLAVE_DATABASES", []):
                with use_master:
                    try:
                        return Export.objects.get(pk=export_id)
                    except Export.DoesNotExist:
                        pass

    return create_export_object(xform, export_type, options)


def get_entity_list_dataset(entity_list: EntityList) -> Iterator[dict]:
    """Get entity data for a an EntityList dataset

    Args:
        entity_list (EntityList): The EntityList whose data
        will be returned

    Returns:
        An iterator of dicts which represent the json data for
        Entities belonging to the dataset
    """
    entities = Entity.objects.filter(entity_list=entity_list, deleted_at__isnull=True)
    dataset_properties = entity_list.properties

    for entity in queryset_iterator(entities):
        data = {
            "name": entity.uuid,
            "label": entity.json.get("label", ""),
        }
        for prop in dataset_properties:
            data[prop] = entity.json.get(prop, "")

        yield data


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
@retry(MAX_RETRIES)
def generate_export(export_type, xform, export_id=None, options=None):  # noqa C901
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
        index_tag: ('[', ']') or ('_', '_')
        show_choice_labels: boolean flag
        language: language labels as in the XLSForm/XForm
    """
    username = xform.user.username
    id_string = xform.id_string

    if options is None:
        options = {}

    end = options.get("end")
    extension = options.get("extension", export_type)
    filter_query = options.get("query")
    remove_group_name = options.get("remove_group_name", False)
    start = options.get("start")
    sort = options.get("sort")
    export_type_func_map = {
        Export.XLSX_EXPORT: "to_xlsx_export",
        Export.CSV_EXPORT: "to_flat_csv_export",
        Export.CSV_ZIP_EXPORT: "to_zipped_csv",
        Export.SAV_ZIP_EXPORT: "to_zipped_sav",
        Export.GOOGLE_SHEETS_EXPORT: "to_google_sheets",
    }

    if xform is None:
        xform = XForm.objects.get(
            user__username__iexact=username, id_string__iexact=id_string
        )

    dataview = None
    if options.get("dataview_pk"):
        dataview = DataView.objects.get(pk=options.get("dataview_pk"))
        records = dataview.query_data(
            dataview,
            all_data=True,
            filter_query=filter_query,
            sort=sort,
        )
        total_records = dataview.query_data(
            dataview,
            count=True,
            sort=sort,
        )[
            0
        ].get("count")
    else:
        records = query_data(
            xform,
            query=filter_query,
            start=start,
            end=end,
            sort=sort,
        )

        if filter_query:
            total_records = query_count(
                xform,
                query=filter_query,
                date_created_gte=start,
                date_created_lte=end,
            )
        else:
            total_records = xform.num_of_submissions

    if isinstance(records, QuerySet):
        records = records.iterator()

    export_builder = ExportBuilder()
    export_builder.TRUNCATE_GROUP_TITLE = (  # noqa
        True if export_type == Export.SAV_ZIP_EXPORT else remove_group_name
    )
    export_builder.GROUP_DELIMITER = options.get(  # noqa
        "group_delimiter", DEFAULT_GROUP_DELIMITER
    )
    export_builder.SPLIT_SELECT_MULTIPLES = options.get(  # noqa
        "split_select_multiples", True
    )
    export_builder.BINARY_SELECT_MULTIPLES = options.get(  # noqa
        "binary_select_multiples", False
    )
    export_builder.INCLUDE_LABELS = options.get("include_labels", False)  # noqa
    include_reviews = options.get("include_reviews", False)
    export_builder.INCLUDE_LABELS_ONLY = options.get(  # noqa
        "include_labels_only", False
    )
    export_builder.INCLUDE_HXL = options.get("include_hxl", False)  # noqa

    export_builder.INCLUDE_IMAGES = options.get(  # noqa
        "include_images", settings.EXPORT_WITH_IMAGE_DEFAULT
    )

    export_builder.VALUE_SELECT_MULTIPLES = options.get(  # noqa
        "value_select_multiples", False
    )

    export_builder.REPEAT_INDEX_TAGS = options.get(  # noqa
        "repeat_index_tags", DEFAULT_INDEX_TAGS
    )

    export_builder.SHOW_CHOICE_LABELS = options.get("show_choice_labels", False)  # noqa

    export_builder.language = options.get("language")
    if export_builder.language is None and xform.default_language != "default":
        export_builder.language = xform.default_language

    # 'win_excel_utf8' is only relevant for CSV exports
    if "win_excel_utf8" in options and export_type != Export.CSV_EXPORT:
        del options["win_excel_utf8"]
    export_builder.INCLUDE_REVIEWS = include_reviews  # noqa
    export_builder.set_survey(xform.survey, xform, include_reviews=include_reviews)

    temp_file = NamedTemporaryFile(suffix="." + extension)

    columns_with_hxl = export_builder.INCLUDE_HXL and get_columns_with_hxl(
        xform.survey_elements
    )

    # get the export function by export type
    func = getattr(export_builder, export_type_func_map[export_type])
    # pylint: disable=broad-except
    try:
        func(
            temp_file.name,
            records,
            username,
            id_string,
            filter_query,
            start=start,
            end=end,
            dataview=dataview,
            xform=xform,
            options=options,
            columns_with_hxl=columns_with_hxl,
            total_records=total_records,
        )
    except NoRecordsFoundError:
        pass
    except SPSSIOError as error:
        export = get_or_create_export(export_id, xform, export_type, options)
        export.error_message = str(error)
        export.internal_status = Export.FAILED
        export.save()
        report_exception("SAV Export Failure", error, sys.exc_info())
        return export

    # generate filename
    basename = f'{id_string}_{datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")}'

    if remove_group_name:
        # add 'remove group name' flag to filename
        basename = f"{basename}-{GROUPNAME_REMOVED_FLAG}"
    if dataview:
        basename = f"{basename}-{DATAVIEW_EXPORT}"

    filename = basename + "." + extension

    # check filename is unique
    while not Export.is_filename_unique(xform, filename):
        filename = increment_index_in_filename(filename)

    file_path = os.path.join(username, "exports", id_string, export_type, filename)

    # seek to the beginning as required by storage classes
    temp_file.seek(0)
    export_filename = default_storage.save(file_path, File(temp_file, file_path))
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
    """
    Return an export object that has not been saved to the database.
    """
    export_options = get_export_options(options)
    return Export(
        xform=xform,
        export_type=export_type,
        options=export_options,
        created_on=timezone.now(),
    )


def check_pending_export(
    xform, export_type, options, minutes=getattr(settings, "PENDING_EXPORT_TIME", 5)
):
    """
    Check for pending export done within a specific period of time and
    returns the export
    :param xform:
    :param export_type:
    :param options:
    :param minutes
    :return:
    """
    created_time = timezone.now() - timedelta(minutes=minutes)
    export_options_kwargs = get_export_options_query_kwargs(options)
    export = Export.objects.filter(
        xform=xform,
        export_type=export_type,
        internal_status=Export.PENDING,
        created_on__gt=created_time,
        **export_options_kwargs,
    ).last()

    return export


def should_create_new_export(
    instance, export_type, options, request=None, is_generic=False
):
    """
    Function that determines whether to create a new export.
    param: xform
    param: export_type
    param: options: additional parameters required for the lookup.
        remove_group_name: boolean flag
        group_delimiter: "/" or "." with "/" as the default
        split_select_multiples: boolean flag
        binary_select_multiples: boolean flag
        index_tag: ('[', ']') or ('_', '_')
    params: request: Get params are used to determine if new export is required
    """
    split_select_multiples = options.get("split_select_multiples", True)

    if getattr(settings, "SHOULD_ALWAYS_CREATE_NEW_EXPORT", False):
        return True

    if (
        request
        and (frozenset(list(request.GET)) & frozenset(["start", "end", "data_id"]))
    ) or not split_select_multiples:
        return True

    export_options_kwargs = get_export_options_query_kwargs(options)

    if is_generic:
        export_qs = GenericExport.objects.filter(
            content_type=GenericExport.get_object_content_type(instance),
            object_id=instance.id,
            export_type=export_type,
            **export_options_kwargs,
        )
    else:
        export_qs = Export.objects.filter(
            xform=instance, export_type=export_type, **export_options_kwargs
        )

    if options.get(EXPORT_QUERY_KEY) is None:
        export_qs = export_qs.exclude(options__has_key=EXPORT_QUERY_KEY)

    if is_generic:
        return not export_qs.exists() or bool(
            GenericExport.exports_outdated(instance, export_type, options=options)
        )

    return not export_qs.exists() or bool(
        Export.exports_outdated(instance, export_type, options=options)
    )


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
        index_tag: ('[', ']') or ('_', '_')
    """

    export_options_kwargs = get_export_options_query_kwargs(options)
    export_query = Export.objects.filter(
        xform=xform, export_type=export_type, **export_options_kwargs
    )

    return export_query.latest("created_on")


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
    new_filename = f"{basename}-{index}{ext}"

    return new_filename


# pylint: disable=too-many-arguments, too-many-positional-arguments
def generate_attachments_zip_export(
    export_type, username, id_string, export_id=None, options=None, xform=None
):
    """
    Generates zip export of attachments.

    param: export_type
    params: username: logged in username
    params: id_string: xform id_string
    params: export_id: ID of export object associated with the request
    param: options: additional parameters required for the lookup.
        ext: File extension of the generated export
    """
    export_type = options.get("extension", export_type)
    filter_query = options.get("query")
    sort = options.get("sort")

    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)

    attachment_qs = Attachment.objects.filter(
        instance__deleted_at__isnull=True,
        deleted_at__isnull=True,
    )

    if options.get("dataview_pk"):
        dataview = DataView.objects.get(pk=options.get("dataview_pk"))
        attachment_qs = attachment_qs.filter(
            instance_id__in=[
                rec.get("_id")
                for rec in dataview.query_data(
                    dataview,
                    all_data=True,
                    filter_query=filter_query,
                    sort=sort,
                )
            ],
        )
    else:
        instance_ids = query_fields_data(
            xform, fields=["_id"], query=filter_query, sort=sort
        )
        if xform.is_merged_dataset:
            attachment_qs = attachment_qs.filter(
                instance__xform_id__in=list(
                    xform.mergedxform.xforms.filter(
                        deleted_at__isnull=True
                    ).values_list("id", flat=True)
                )
            ).filter(instance_id__in=[i_id["_id"] for i_id in instance_ids])
        else:
            attachment_qs = attachment_qs.filter(instance__xform_id=xform.pk).filter(
                instance_id__in=[i_id["_id"] for i_id in instance_ids]
            )

    filename = (
        f'{id_string}_{datetime.now().strftime("%Y_%m_%d_%H_%M_%S")}'
        f".{export_type.lower()}"
    )
    file_path = os.path.join(username, "exports", id_string, export_type, filename)
    zip_file = None

    with NamedTemporaryFile() as zip_file:
        create_attachments_zipfile(attachment_qs, zip_file)
        with open(zip_file.name, "rb") as temp_file:
            filename = default_storage.save(file_path, File(temp_file, file_path))

    export = get_or_create_export(export_id, xform, export_type, options)
    export.filedir, export.filename = os.path.split(filename)
    export.internal_status = Export.SUCCESSFUL
    export.save()

    return export


def write_temp_file_to_path(suffix, content, file_path):
    """Write a temp file and return the name of the file.
    :param suffix: The file suffix
    :param content: The content to write
    :param file_path: The path to write the temp file to
    :return: The filename written to
    """
    temp_file = NamedTemporaryFile(suffix=suffix)
    temp_file.write(content)
    temp_file.seek(0)
    export_filename = default_storage.save(file_path, File(temp_file, file_path))
    temp_file.close()

    return export_filename


def get_or_create_export_object(export_id, options, xform, export_type):
    """Get or create export object.

    :param export_id: Export ID
    :param options: Options to convert to export options
    :param xform: XForm to export
    :param export_type: The type of export
    :return: A new or found export object
    """
    if export_id and Export.objects.filter(pk=export_id).exists():
        try:
            export = Export.objects.get(id=export_id)
        except Export.DoesNotExist:
            with use_master:
                try:
                    return Export.objects.get(pk=export_id)
                except Export.DoesNotExist:
                    pass
    else:
        export_options = get_export_options(options)
        export = Export.objects.create(
            xform=xform, export_type=export_type, options=export_options
        )

    return export


# pylint: disable=too-many-arguments, too-many-positional-arguments
def generate_kml_export(
    export_type, username, id_string, export_id=None, options=None, xform=None
):
    """
    Generates kml export for geographical data

    :param export_type: type of export
    :param username: logged in username
    :param id_string: xform id_string
    :param export_id: ID of export object associated with the request
    :param options: additional parameters required for the lookup.
    :param extension: File extension of the generated export
    """
    export_type = options.get("extension", export_type)

    user = User.objects.get(username=username)
    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)

    response = render(
        None, "survey.kml", {"data": kml_export_data(id_string, user, xform=xform)}
    )

    basename = f'{id_string}_{datetime.now().strftime("%Y_%m_%d_%H_%M_%S")}'
    filename = basename + "." + export_type.lower()
    file_path = os.path.join(username, "exports", id_string, export_type, filename)

    export_filename = write_temp_file_to_path(
        export_type.lower(), response.content, file_path
    )

    export = get_or_create_export_object(export_id, options, xform, export_type)

    export.filedir, export.filename = os.path.split(export_filename)
    export.internal_status = Export.SUCCESSFUL
    export.save()

    return export


def get_query_params_from_metadata(metadata):
    """
    Build out query params to be used in GeoJsonSerializer
    """
    extra_data = metadata.extra_data or {}

    return {
        mapped_key: extra_data[original_key]
        for original_key, mapped_key in GEOJSON_EXTRA_DATA_EXPORT_OPTION_MAP.items()
        if original_key in extra_data
    }


def generate_geojson_export(
    export_type,
    username,
    id_string,
    export_id=None,
    options=None,
    xform=None,
):
    """
    Generates Linked Geojson export

    :param export_type: type of export
    :param username: logged in username
    :param id_string: xform id_string
    :param export_id: ID of export object associated with the request
    :param options: additional parameters required for the lookup.
    :param xform: XForm to export
    """

    extension = options.get("extension", export_type)
    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)
    request = HttpRequest()
    request.query_params = {
        param: options.get(param)
        for param in GEOJSON_EXTRA_DATA_EXPORT_OPTION_MAP.values()
        if param in options
    }
    _context = {}
    _context["request"] = request
    # filter out deleted submissions
    content = GeoJsonSerializer(
        xform.instances.filter(deleted_at__isnull=True), many=True, context=_context
    )
    data_to_write = json.dumps(content.data).encode("utf-8")
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    basename = f"{id_string}_{timestamp}"
    filename = basename + "." + extension
    file_path = os.path.join(username, "exports", id_string, export_type, filename)

    export_filename = write_temp_file_to_path(extension, data_to_write, file_path)

    export = get_or_create_export_object(export_id, options, xform, export_type)

    dir_name, basename = os.path.split(export_filename)
    export.filedir = dir_name
    export.filename = basename
    export.internal_status = Export.SUCCESSFUL
    export.save()

    return export


def kml_export_data(id_string, user, xform=None):
    """
    KML export data from form submissions.
    """

    def cached_get_labels(xpath):
        """
        Get and Cache labels for the XForm.
        """
        if xpath in list(labels):
            return labels[xpath]
        labels[xpath] = xform.get_label(xpath)

        return labels[xpath]

    xform = xform or XForm.objects.get(id_string=id_string, user=user)

    data_kwargs = {"geom__isnull": False}
    if xform.is_merged_dataset:
        data_kwargs.update(
            {
                "xform_id__in": list(
                    xform.mergedxform.xforms.filter(
                        deleted_at__isnull=True
                    ).values_list("id", flat=True)
                )
            }
        )
    else:
        data_kwargs.update({"xform_id": xform.pk})
    instances = Instance.objects.filter(**data_kwargs).order_by("id")
    data_for_template = []
    labels = {}
    for instance in queryset_iterator(instances):
        # read the survey instances
        data_for_display = instance.get_dict()
        xpaths = list(data_for_display)
        xpaths.sort(key=cmp_to_key(instance.xform.get_xpath_cmp()))
        table_rows = [
            f"<tr><td>{cached_get_labels(xpath) }</td>"
            f"<td>{data_for_display[xpath]}</td></tr>"
            for xpath in xpaths
            if not xpath.startswith("_")
        ]
        img_urls = image_urls(instance)

        if instance.point:
            img_url = img_urls[0] if img_urls else ""
            rows = "".join(table_rows)
            data_for_template.append(
                {
                    "name": instance.xform.id_string,
                    "id": instance.id,
                    "lat": instance.point.y,
                    "lng": instance.point.x,
                    "image_urls": img_urls,
                    "table": '<table border="1"><a href="#"><img width="210" '
                    f'class="thumbnail" src="{img_url}" alt=""></a>{rows}'
                    "</table>",
                }
            )

    return data_for_template


def get_osm_data_kwargs(xform):
    """Return kwargs for OsmData queryset for given xform"""

    kwargs = {"instance__deleted_at__isnull": True}

    if xform.is_merged_dataset:
        kwargs["instance__xform_id__in"] = list(
            xform.mergedxform.xforms.filter(deleted_at__isnull=True).values_list(
                "id", flat=True
            )
        )
    else:
        kwargs["instance__xform_id"] = xform.pk

    return kwargs


def generate_osm_export(
    export_type, username, id_string, export_id=None, options=None, xform=None
):
    """
    Generates osm export for OpenStreetMap data

    :param export_type: type of export
    :param username: logged in username
    :param id_string: xform id_string
    :param export_id: ID of export object associated with the request
    :param options: additional parameters required for the lookup.
    :param ext: File extension of the generated export
    """

    extension = options.get("extension", export_type)

    if xform is None:
        xform = XForm.objects.get(user__username=username, id_string=id_string)

    kwargs = get_osm_data_kwargs(xform)
    osm_list = OsmData.objects.filter(**kwargs)
    content = get_combined_osm(osm_list)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    basename = f"{id_string}_{timestamp}"
    filename = basename + "." + extension
    file_path = os.path.join(username, "exports", id_string, export_type, filename)

    export_filename = write_temp_file_to_path(extension, content, file_path)

    export = get_or_create_export_object(export_id, options, xform, export_type)

    dir_name, basename = os.path.split(export_filename)
    export.filedir = dir_name
    export.filename = basename
    export.internal_status = Export.SUCCESSFUL
    export.save()

    return export


def _get_records(instances):
    return [clean_keys_of_slashes(instance) for instance in instances]


def clean_keys_of_slashes(record):
    """
    Replaces the slashes found in a dataset keys with underscores
    :param record: list containing a couple of dictionaries
    :return: record with keys without slashes
    """
    for key in list(record):
        value = record[key]
        if "/" in key:
            # replace with _
            record[key.replace("/", "_")] = record.pop(key)
        # Check if the value is a list containing nested dict and apply same
        if value:
            if isinstance(value, list) and isinstance(value[0], dict):
                for item in value:
                    clean_keys_of_slashes(item)

    return record


def _get_server_from_metadata(xform, meta, token):
    # Fetch metadata details from master directly
    try:
        report_templates = MetaData.external_export(xform)
    except MetaData.DoesNotExist:
        with use_master:
            report_templates = MetaData.external_export(xform)

    if meta:
        try:
            int(meta)
        except ValueError as error:
            raise ValueError(f"Invalid metadata pk {meta}") from error

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
            raise ValueError(
                "Could not find the template token: Please upload template."
            )

        server = report_templates[0].external_export_url
        name = report_templates[0].external_export_name

    return server, name


def generate_external_export(  # noqa C901
    export_type, username, id_string, export_id=None, options=None, xform=None
):
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
    sort = options.get("sort")

    if xform is None:
        xform = XForm.objects.get(
            user__username__iexact=username, id_string__iexact=id_string
        )
    user = User.objects.get(username=username)

    server, name = _get_server_from_metadata(xform, meta, token)

    # dissect the url
    parsed_url = urlparse(server)

    token = parsed_url.path[5:]

    ser = parsed_url.scheme + "://" + parsed_url.netloc

    # Get single submission data
    if data_id:
        inst = Instance.objects.filter(
            xform__user=user, xform__id_string=id_string, deleted_at=None, pk=data_id
        )

        instances = [inst[0].json if inst else {}]
    else:
        instances = query_data(
            xform,
            query=filter_query,
            sort=sort,
        )

    records = _get_records(instances)

    response = ""
    status_code = 0

    if records and server:
        try:
            client = Client(ser)
            response = client.xls.create(token, json.dumps(records))

            if hasattr(client.xls.conn, "last_response"):
                status_code = client.xls.conn.last_response.status_code
        except Exception as error:
            raise J2XException(
                f"J2X client could not generate report. Server -> {server},"
                f" Error-> {error}"
            ) from error
    else:
        if not server:
            raise J2XException("External server not set")
        if not records:
            raise J2XException(f"No record to export. Form -> {id_string}")

    # get or create export object
    if export_id:
        try:
            export = Export.objects.get(id=export_id)
        except Export.DoesNotExist:
            with use_master:
                export = Export.objects.get(id=export_id)
    else:
        export_options = get_export_options(options)
        export = Export.objects.create(
            xform=xform, export_type=export_type, options=export_options
        )

    export.export_url = response
    if status_code == 201:
        export.internal_status = Export.SUCCESSFUL
        export.filename = name + "-" + response[5:] if name else response[5:]
        export.export_url = ser + response
    else:
        export.internal_status = Export.FAILED

    export.save()

    return export


def upload_template_for_external_export(server, file_obj):
    """
    Uploads an Excel template to the XLSReport server.

    Returns the status code with the server response.
    """
    client = Client(server)
    response = client.template.create(template_file=file_obj)
    status_code = None

    if hasattr(client.template.conn, "last_response"):
        status_code = client.template.conn.last_response.status_code

    return str(status_code) + "|" + response


# pylint: disable=too-many-branches
def parse_request_export_options(params):  # noqa C901
    """
    Parse export options in the request object into values returned in a
    list. The list represents a boolean for whether the group name should be
    removed, the group delimiter, and a boolean for whether select multiples
    should be split.
    """
    boolean_list = ["true", "false"]
    options = {}
    remove_group_name = (
        params.get("remove_group_name") and params.get("remove_group_name").lower()
    )
    binary_select_multiples = (
        params.get("binary_select_multiples")
        and params.get("binary_select_multiples").lower()
    )
    do_not_split_select_multiples = params.get("do_not_split_select_multiples")
    include_labels = params.get("include_labels", False)
    include_reviews = params.get("include_reviews", False)
    include_labels_only = params.get("include_labels_only", False)
    include_hxl = params.get("include_hxl", True)
    value_select_multiples = (
        params.get("value_select_multiples")
        and params.get("value_select_multiples").lower()
    )
    show_choice_labels = (
        params.get("show_choice_labels") and params.get("show_choice_labels").lower()
    )

    if include_labels is not None:
        options["include_labels"] = str_to_bool(include_labels)

    if include_reviews is not None:
        options["include_reviews"] = str_to_bool(include_reviews)

    if include_labels_only is not None:
        options["include_labels_only"] = str_to_bool(include_labels_only)

    if include_hxl is not None:
        options["include_hxl"] = str_to_bool(include_hxl)

    if remove_group_name in boolean_list:
        options["remove_group_name"] = str_to_bool(remove_group_name)
    else:
        options["remove_group_name"] = False

    if params.get("group_delimiter") in [".", DEFAULT_GROUP_DELIMITER]:
        options["group_delimiter"] = params.get("group_delimiter")
    else:
        options["group_delimiter"] = DEFAULT_GROUP_DELIMITER

    options["split_select_multiples"] = not str_to_bool(do_not_split_select_multiples)
    if binary_select_multiples and binary_select_multiples in boolean_list:
        options["binary_select_multiples"] = str_to_bool(binary_select_multiples)

    if "include_images" in params:
        options["include_images"] = str_to_bool(params.get("include_images"))
    else:
        options["include_images"] = settings.EXPORT_WITH_IMAGE_DEFAULT

    options["win_excel_utf8"] = str_to_bool(params.get("win_excel_utf8"))

    if value_select_multiples and value_select_multiples in boolean_list:
        options["value_select_multiples"] = str_to_bool(value_select_multiples)

    if show_choice_labels and show_choice_labels in boolean_list:
        options["show_choice_labels"] = str_to_bool(show_choice_labels)

    index_tags = get_repeat_index_tags(params.get("repeat_index_tags"))
    if index_tags:
        options["repeat_index_tags"] = index_tags

    if "language" in params:
        options["language"] = params.get("language")

    return options


def get_repeat_index_tags(index_tags):
    """
    Gets a comma separated string `index_tags`

    Retuns a tuple of two strings with  SUPPORTED_INDEX_TAGS,
    """
    if isinstance(index_tags, six.string_types):
        index_tags = tuple(index_tags.split(","))
        length = len(index_tags)
        if length == 1:
            index_tags = (index_tags[0], index_tags[0])
        elif length > 1:
            index_tags = index_tags[:2]
        else:
            index_tags = DEFAULT_INDEX_TAGS

        for tag in index_tags:
            if tag not in SUPPORTED_INDEX_TAGS:
                raise exceptions.ParseError(
                    _(
                        f"The tag {tag} is not supported, "
                        f"supported tags are {SUPPORTED_INDEX_TAGS}"
                    )
                )

    return index_tags


def generate_entity_list_export(entity_list: EntityList) -> GenericExport:
    """Generates a CSV for an EntityList dataset"""
    username = entity_list.project.organization.username
    records = get_entity_list_dataset(entity_list)
    export_builder = ExportBuilder()
    extension = Export.CSV_EXPORT
    temp_file = NamedTemporaryFile(suffix="." + extension)
    export_builder.to_flat_csv_export(
        temp_file.name, records, username, None, None, entity_list=entity_list
    )
    # Generate filename
    basename = f'{entity_list.name}_{datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")}'
    filename = basename + "." + extension

    # Check filename is unique
    while not GenericExport.is_filename_unique(entity_list, filename):
        filename = increment_index_in_filename(filename)

    file_path = os.path.join(
        username, "exports", entity_list.name, Export.CSV_EXPORT, filename
    )
    # seek to the beginning as required by storage classes
    temp_file.seek(0)
    export_filename = default_storage.save(file_path, File(temp_file, file_path))
    temp_file.close()
    dir_name, basename = os.path.split(export_filename)
    # Create export object
    export = GenericExport.objects.create(
        content_object=entity_list,
        export_type=Export.CSV_EXPORT,
        filedir=dir_name,
        filename=basename,
        internal_status=Export.SUCCESSFUL,
    )
    return export


def get_latest_generic_export(
    instance, export_type, options=None
) -> GenericExport | None:
    """Retrieve the latest GenericExport"""
    export_options_kwargs = get_export_options_query_kwargs(options)
    object_content_type = GenericExport.get_object_content_type(instance)
    export_query = GenericExport.objects.filter(
        content_type=object_content_type,
        object_id=instance.id,
        export_type=export_type,
        **export_options_kwargs,
    )

    try:
        latest_export = export_query.latest("created_on")

    except GenericExport.DoesNotExist:
        return None

    return latest_export


def get_dataview_export_options(data_view):
    """
    Get the export options for a dataview.

    :param data_view: DataView instance
    :return: Export options
    """
    # Avoid circular import
    api_export_tools = importlib.import_module("onadata.libs.utils.api_export_tools")

    export_options = {
        "dataview_pk": data_view.pk,
    }

    xform = data_view.xform
    columns_with_hxl = get_columns_with_hxl(xform.survey.get("children"))

    if columns_with_hxl:
        export_options["include_hxl"] = api_export_tools.include_hxl_row(
            data_view.columns, list(columns_with_hxl)
        )

    return export_options
