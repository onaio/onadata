# -*- coding: utf-8 -*-
"""Utility functions for data views."""

import json
import os
import sys
import zipfile
from json.decoder import JSONDecodeError
from typing import Dict

from django.conf import settings
from django.core.files.storage import storages
from django.utils.translation import gettext as _

import requests
from defusedxml import minidom
from six.moves.urllib.parse import urljoin

from onadata.libs.exceptions import EnketoError
from onadata.libs.utils import common_tags
from onadata.libs.utils.common_tags import EXPORT_MIMES
from onadata.libs.utils.common_tools import report_exception

SLASH = "/"


def image_urls_for_form(xform):
    """Return image urls of all image attachments of the xform."""
    return sum(
        [image_urls(s) for s in xform.instances.filter(deleted_at__isnull=True)], []
    )


def get_path(path, suffix):
    """Apply the suffix to the path."""
    filename, file_extension = os.path.splitext(path)

    return filename + suffix + file_extension


def image_urls(instance):
    """
    Return image urls of all image attachments of the submission instance.

    arguments:
    instance -- Instance submission object.
    """
    default_storage = storages["default"]
    urls = []
    suffix = settings.THUMB_CONF["medium"]["suffix"]
    for attachment in instance.attachments.all():
        path = get_path(attachment.media_file.name, suffix)
        if default_storage.exists(path):
            url = default_storage.url(path)
        else:
            url = attachment.media_file.url
        urls.append(url)

    return urls


def parse_xform_instance(xml_str):
    """'xml_str' is a str object holding the XML of an XForm instance.

    Return a python object representation of this XML file.
    """
    xml_obj = minidom.parseString(xml_str)
    root_node = xml_obj.documentElement
    # go through the xml object creating a corresponding python object
    # NOTE: THIS WILL DESTROY ANY DATA COLLECTED WITH REPEATABLE NODES
    # THIS IS OKAY FOR OUR USE CASE, BUT OTHER USERS SHOULD BEWARE.
    survey_data = dict(_path_value_pairs(root_node))
    if len(list(_all_attributes(root_node))) != 1:
        raise AssertionError(
            _("There should be exactly one attribute in this document.")
        )
    survey_data.update(
        {
            common_tags.XFORM_ID_STRING: root_node.getAttribute("id"),
            common_tags.INSTANCE_DOC_NAME: root_node.nodeName,
        }
    )

    return survey_data


def _path(node):
    _node = node
    levels = []
    while _node.nodeType != _node.DOCUMENT_NODE:
        levels = [_node.nodeName] + levels
        _node = _node.parentNode
    return SLASH.join(levels[1:])


def _path_value_pairs(node):
    """
    Using a depth first traversal of the xml nodes build up a python
    object in parent that holds the tree structure of the data.
    """
    if node.childNodes:
        # there's no data for this leaf node
        yield _path(node), None
    elif len(node.childNodes) == 1 and node.childNodes[0].nodeType == node.TEXT_NODE:
        # there is data for this leaf node
        yield _path(node), node.childNodes[0].nodeValue
    else:
        # this is an internal node
        for child in node.childNodes:
            yield from _path_value_pairs(child)


def _all_attributes(node):
    """Go through an XML document returning all the attributes we see."""
    if hasattr(node, "hasAttributes") and node.hasAttributes():
        for key in list(node.attributes):
            yield key, node.getAttribute(key)
    for child in node.childNodes:
        yield from _all_attributes(child)


def export_def_from_filename(filename):
    """Return file extension and mimetype from filename."""
    __, ext = os.path.splitext(filename)
    ext = ext[1:]
    mime_type = EXPORT_MIMES[ext]

    return ext, mime_type


def get_client_ip(request):
    """Return an IP from HTTP_X_FORWARDED_FOR or REMOTE_ADDR request headers.

    arguments:
    request -- HttpRequest object.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]

    return request.META.get("REMOTE_ADDR")


def get_enketo_urls(
    form_url, id_string, instance_xml=None, instance_id=None, return_url=None, **kwargs
) -> Dict[str, str]:
    """Return Enketo URLs."""
    if (
        not hasattr(settings, "ENKETO_URL")
        or not hasattr(settings, "ENKETO_API_ALL_SURVEY_LINKS_PATH")
        or not hasattr(settings, "ENKETO_API_TOKEN")
        or settings.ENKETO_API_TOKEN == ""
    ):
        return False

    url = urljoin(settings.ENKETO_URL, settings.ENKETO_API_ALL_SURVEY_LINKS_PATH)

    values = {"form_id": id_string, "server_url": form_url}
    if instance_id is not None and instance_xml is not None:
        url = urljoin(settings.ENKETO_URL, settings.ENKETO_API_INSTANCE_PATH)
        values.update(
            {
                "instance": instance_xml,
                "instance_id": instance_id,
                # convert to unicode string in python3 compatible way
                "return_url": f"{return_url}",
            }
        )

    if kwargs:
        # Kwargs need to take note of xform variable paths i.e.
        # kwargs = {'defaults[/widgets/text_widgets/my_string]': "Hey Mark"}
        values.update(kwargs)

    response = requests.post(
        url,
        data=values,
        auth=(settings.ENKETO_API_TOKEN, ""),
        verify=getattr(settings, "VERIFY_SSL", True),
        timeout=20,
    )
    resp_content = response.content
    resp_content = (
        resp_content.decode("utf-8")
        if hasattr(resp_content, "decode")
        else resp_content
    )
    if response.status_code in [200, 201]:
        try:
            data = json.loads(resp_content)
        except ValueError:
            pass
        else:
            if data:
                return data

    handle_enketo_error(response)

    return None


def handle_enketo_error(response):
    """Handle enketo error response."""
    try:
        data = json.loads(response.content)
    except (ValueError, JSONDecodeError) as enketo_error:
        report_exception(
            f"HTTP Error {response.status_code}", response.text, sys.exc_info()
        )
        if response.status_code == 502:
            raise EnketoError(
                "Sorry, we cannot load your form right now.  Please try again later."
            ) from enketo_error
        raise EnketoError() from enketo_error
    if "message" in data:
        raise EnketoError(data["message"])
    raise EnketoError(response.text)


def generate_enketo_form_defaults(xform, **kwargs):
    """Return Enketo default options for preloading data into a web form."""
    defaults = {}

    if kwargs:
        for name, value in kwargs.items():
            field = xform.get_survey_element(name)
            if field:
                defaults[f"defaults[{field.get_xpath()}]"] = value

    return defaults


def create_attachments_zipfile(attachments, zip_file):
    """Return a zip file with submission attachments.

    :param attachments: an Attachments queryset.
    :param zip_file: a file object, more likely a NamedTemporaryFile() object.
    """
    with zipfile.ZipFile(
        zip_file, "w", zipfile.ZIP_DEFLATED, allowZip64=True
    ) as z_file:
        for attachment in attachments:
            default_storage = storages["default"]
            filename = attachment.media_file.name

            if default_storage.exists(filename):
                try:
                    with default_storage.open(filename) as a_file:
                        if a_file.size > settings.ZIP_REPORT_ATTACHMENT_LIMIT:
                            report_exception(
                                "Create attachment zip exception",
                                (
                                    "File is greater than "
                                    f"{settings.ZIP_REPORT_ATTACHMENT_LIMIT} bytes"
                                ),
                            )
                            break
                        z_file.writestr(attachment.media_file.name, a_file.read())
                except IOError as io_error:
                    report_exception("Create attachment zip exception", io_error)
                    break


def get_form(kwargs):
    """Return XForm object by applying kwargs on an XForm queryset."""
    # adding inline imports here because adding them at the top of the file
    # triggers the following error:
    # django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.
    # pylint: disable=import-outside-toplevel
    from django.http import Http404

    from onadata.apps.logger.models import XForm

    queryset = kwargs.pop("queryset", XForm.objects.all())
    kwargs["deleted_at__isnull"] = True
    xform = queryset.filter(**kwargs).first()
    if xform:
        return xform

    raise Http404("XForm does not exist.")


# pylint: disable=too-many-arguments, too-many-positional-arguments
def get_form_url(
    request,
    username=None,
    protocol="https",
    preview=False,
    xform_pk=None,
    generate_consistent_urls=False,
):
    """
    Return a form list url endpoint to be used to make a request to Enketo.

    For example, it will return https://example.com and Enketo will know to
    look for the form list at https://example.com/formList. If a username is
    provided then Enketo will request the form list from
    https://example.com/[username]/formList. Same applies for preview if
    preview is True and also to a single form when xform_pk is provided.
    """
    if settings.TESTING_MODE:
        http_host = settings.TEST_HTTP_HOST
        username = settings.TEST_USERNAME
    else:
        http_host = request.headers.get("Host", "ona.io")

    url = f"{protocol}://{http_host}"

    if preview:
        url += "/preview"

    if xform_pk and generate_consistent_urls:
        url += f"/enketo/{xform_pk}"
    elif username:
        url += f"/{username}/{xform_pk}" if xform_pk else f"/{username}"

    return url
