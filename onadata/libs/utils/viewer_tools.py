# -*- coding: utf-8 -*-
"""Util functions for data views."""
import json
import os
import sys
import zipfile
from builtins import open
from tempfile import NamedTemporaryFile
from xml.dom import minidom

import requests
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import ugettext as _
from future.moves.urllib.parse import urljoin
from future.utils import iteritems

from onadata.libs.exceptions import EnketoError
from onadata.libs.utils import common_tags
from onadata.libs.utils.common_tags import EXPORT_MIMES
from onadata.libs.utils.common_tools import report_exception

SLASH = u"/"


def image_urls_for_form(xform):
    """Return image urls of all image attachments of the xform."""
    return sum(
        [
            image_urls(s)
            for s in xform.instances.filter(deleted_at__isnull=True)
        ], [])


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
    default_storage = get_storage_class()()
    urls = []
    suffix = settings.THUMB_CONF['medium']['suffix']
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
        raise AssertionError(_(
            u"There should be exactly one attribute in this document."))
    survey_data.update({
        common_tags.XFORM_ID_STRING:
        root_node.getAttribute(u"id"),
        common_tags.INSTANCE_DOC_NAME:
        root_node.nodeName,
    })

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
    elif len(node.childNodes) == 1 and \
            node.childNodes[0].nodeType == node.TEXT_NODE:
        # there is data for this leaf node
        yield _path(node), node.childNodes[0].nodeValue
    else:
        # this is an internal node
        for child in node.childNodes:
            for pair in _path_value_pairs(child):
                yield pair


def _all_attributes(node):
    """Go through an XML document returning all the attributes we see."""
    if hasattr(node, "hasAttributes") and node.hasAttributes():
        for key in list(node.attributes):
            yield key, node.getAttribute(key)
    for child in node.childNodes:
        for pair in _all_attributes(child):
            yield pair


def django_file(path, field_name, content_type):
    """Return an InMemoryUploadedFile object for file uploads."""
    # adapted from here: http://groups.google.com/group/django-users/browse_th\
    # read/thread/834f988876ff3c45/
    file_object = open(path, 'rb')

    return InMemoryUploadedFile(
        file=file_object,
        field_name=field_name,
        name=file_object.name,
        content_type=content_type,
        size=os.path.getsize(path),
        charset=None)


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
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]

    return request.META.get('REMOTE_ADDR')


def enketo_url(form_url,
               id_string,
               instance_xml=None,
               instance_id=None,
               return_url=None,
               **kwargs):
    """Return Enketo webform URL."""
    if (not hasattr(settings, 'ENKETO_URL') or
            not hasattr(settings, 'ENKETO_API_SURVEY_PATH') or
            not hasattr(settings, 'ENKETO_API_TOKEN') or
            settings.ENKETO_API_TOKEN == ''):
        return False

    url = urljoin(settings.ENKETO_URL, settings.ENKETO_API_SURVEY_PATH)

    values = {'form_id': id_string, 'server_url': form_url}
    if instance_id is not None and instance_xml is not None:
        url = urljoin(settings.ENKETO_URL, settings.ENKETO_API_INSTANCE_PATH)
        values.update({
            'instance': instance_xml,
            'instance_id': instance_id,
            # convert to unicode string in python3 compatible way
            'return_url': u'%s' % return_url
        })

    if kwargs:
        # Kwargs need to take note of xform variable paths i.e.
        # kwargs = {'defaults[/widgets/text_widgets/my_string]': "Hey Mark"}
        values.update(kwargs)

    response = requests.post(
        url,
        data=values,
        auth=(settings.ENKETO_API_TOKEN, ''),
        verify=getattr(settings, 'VERIFY_SSL', True))
    if response.status_code in [200, 201]:
        try:
            data = json.loads(response.content)
        except ValueError:
            pass
        else:
            url = (data.get('edit_url') or data.get('offline_url') or
                   data.get('url'))
            if url:
                return url

    handle_enketo_error(response)


def handle_enketo_error(response):
    """Handle enketo error response."""
    try:
        data = json.loads(response.content)
    except ValueError:
        report_exception("HTTP Error {}".format(response.status_code),
                         response.text, sys.exc_info())
        if response.status_code == 502:
            raise EnketoError(
                u"Sorry, we cannot load your form right now.  Please try "
                "again later.")
        raise EnketoError()
    else:
        if 'message' in data:
            raise EnketoError(data['message'])
        raise EnketoError(response.text)


def generate_enketo_form_defaults(xform, **kwargs):
    """Return Enketo default options for preloading data into a web form."""
    defaults = {}

    if kwargs:
        for (name, value) in iteritems(kwargs):
            field = xform.get_survey_element(name)
            if field:
                defaults["defaults[{}]".format(field.get_xpath())] = value

    return defaults


def create_attachments_zipfile(attachments):
    """Return a zip file with submission attachments."""
    # create zip_file
    tmp = NamedTemporaryFile()
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for attachment in attachments:
            default_storage = get_storage_class()()
            filename = attachment.media_file.name

            if default_storage.exists(filename):
                try:
                    with default_storage.open(filename) as f:
                        if f.size > settings.ZIP_REPORT_ATTACHMENT_LIMIT:
                            report_exception(
                                "Create attachment zip exception",
                                "File is greater than {} bytes".format(
                                    settings.ZIP_REPORT_ATTACHMENT_LIMIT)
                            )
                            break
                        else:
                            z.writestr(attachment.media_file.name, f.read())
                except IOError as e:
                    report_exception("Create attachment zip exception", e)
                    break

    return tmp


def get_form(kwargs):
    """Return XForm object by applying kwargs on an XForm queryset."""
    # adding inline imports here because adding them at the top of the file
    # triggers the following error:
    # django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.
    from onadata.apps.logger.models import XForm
    from django.http import Http404

    queryset = kwargs.pop('queryset', XForm.objects.all())
    kwargs['deleted_at__isnull'] = True
    xform = queryset.filter(**kwargs).first()
    if xform:
        return xform

    raise Http404("XForm does not exist.")


def get_form_url(request,
                 username=None,
                 protocol='https',
                 preview=False,
                 xform_pk=None):
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
        http_host = request.META.get('HTTP_HOST', 'ona.io')

    url = '%s://%s' % (protocol, http_host)

    if preview:
        url = '%s/preview' % url

    if username and xform_pk is None:
        url = "{}/{}".format(url, username)
    if username and xform_pk:
        url = "{}/{}/{}".format(url, username, xform_pk)

    return url


def get_enketo_edit_url(request, instance, return_url):
    """Given a submssion instance,
    returns an Enketo link to edit the specified submission."""
    form_url = get_form_url(
        request,
        instance.xform.user.username,
        settings.ENKETO_PROTOCOL,
        xform_pk=instance.xform_id)
    url = enketo_url(
        form_url,
        instance.xform.id_string,
        instance_xml=instance.xml,
        instance_id=instance.uuid,
        return_url=return_url)
    return url


def get_enketo_preview_url(request, username, id_string, xform_pk=None):
    """Return an Enketo preview URL."""
    form_url = get_form_url(
        request, username, settings.ENKETO_PROTOCOL, True, xform_pk=xform_pk)
    values = {'form_id': id_string, 'server_url': form_url}

    response = requests.post(
        settings.ENKETO_PREVIEW_URL,
        data=values,
        auth=(settings.ENKETO_API_TOKEN, ''),
        verify=getattr(settings, 'VERIFY_SSL', True))

    try:
        response = json.loads(response.content)
    except ValueError:
        pass
    else:
        if 'preview_url' in response:
            return response['preview_url']
        elif 'message' in response:
            raise EnketoError(response['message'])

    return False


def get_enketo_single_submit_url(request, username, id_string, xform_pk=None):
    """Return single submit url of the submission instance."""
    enketo_url = urljoin(settings.ENKETO_URL, getattr(
        settings, 'ENKETO_SINGLE_SUBMIT_PATH', "/api/v2/survey/single/once"))
    form_id = id_string
    server_url = get_form_url(
        request, username, settings.ENKETO_PROTOCOL, True, xform_pk=xform_pk)

    url = '{}?server_url={}&form_id={}'.format(
        enketo_url, server_url, form_id)

    response = requests.get(url, auth=(settings.ENKETO_API_TOKEN, ''))

    if response.status_code == 200:
        try:
            data = json.loads(response.content)
        except ValueError:
            pass
        return data['single_url']

    handle_enketo_error(response)
