# -*- coding: utf-8 -*-
"""ODK BriefcaseClient utils module"""
import logging
import mimetypes
import os
from io import StringIO
from xml.parsers.expat import ExpatError

from six.moves.urllib.parse import urljoin

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction

import requests
from requests.auth import HTTPDigestAuth

from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.libs.utils.common_tools import retry
from onadata.libs.utils.logger_tools import PublishXForm, create_instance, publish_form

NUM_RETRIES = 3
DEFAULT_REQUEST_TIMEOUT = 45


def django_file(file_obj, field_name, content_type):
    """Return an InMemoryUploadedFile file object."""
    return InMemoryUploadedFile(
        file=file_obj,
        field_name=field_name,
        name=file_obj.name,
        content_type=content_type,
        size=file_obj.size,
        charset=None,
    )


def node_value(node, tag_name):
    """
    Returns the first nodeValue of of an elementin the node with the matching
    tag_name otherwise returns empty list [].
    """
    child_nodes = node.getElementsByTagName(tag_name)[0].childNodes

    return child_nodes and child_nodes[0].nodeValue


def _get_form_list(xml_text):
    xml_doc = clean_and_parse_xml(xml_text)
    forms = []

    for child_node in xml_doc.childNodes:
        if child_node.nodeName == "xforms":
            for xform_node in child_node.childNodes:
                if xform_node.nodeName == "xform":
                    id_string = node_value(xform_node, "formID")
                    download_url = node_value(xform_node, "downloadUrl")
                    manifest_url = node_value(xform_node, "manifestUrl")
                    forms.append((id_string, download_url, manifest_url))

    return forms


def _get_instances_uuids(xml_doc):
    uuids = []

    for child_node in xml_doc.childNodes:
        if child_node.nodeName == "idChunk":
            for id_node in child_node.getElementsByTagName("id"):
                if id_node.childNodes:
                    uuid = id_node.childNodes[0].nodeValue
                    uuids.append(uuid)

    return uuids


# pylint: disable=too-many-instance-attributes
class BriefcaseClient:
    """ODK BriefcaseClient class"""

    def __init__(self, url, username, password, user):
        self.url = url
        self.user = user
        self.auth = HTTPDigestAuth(username, password)
        self.form_list_url = urljoin(self.url, "formList")
        self.submission_list_url = urljoin(self.url, "view/submissionList")
        self.download_submission_url = urljoin(self.url, "view/downloadSubmission")
        self.forms_path = os.path.join(self.user.username, "briefcase", "forms")
        self.resumption_cursor = 0
        self.logger = logging.getLogger("console_logger")

    def download_manifest(self, manifest_url, id_string):
        """Downloads the XForm manifest from an ODK server."""
        if self._get_response(manifest_url):
            manifest_res = getattr(self, "_current_response")

            try:
                manifest_doc = clean_and_parse_xml(manifest_res.content)
            except ExpatError:
                return

            manifest_path = os.path.join(self.forms_path, id_string, "form-media")
            self.logger.debug("Downloading media files for %s", id_string)

            self.download_media_files(manifest_doc, manifest_path)

    def download_xforms(self, include_instances=False):
        """Downloads the XForm XML form an ODK server."""
        # fetch formList
        if not self._get_response(self.form_list_url):
            _current_response = getattr(self, "_current_response")
            response = (
                _current_response.content if _current_response else "Unknown Error"
            )
            self.logger.error("Failed to download xforms %s.", response)

            return

        response = getattr(self, "_current_response")
        forms = _get_form_list(response.content)

        self.logger.debug("Successfull fetched %s.", self.form_list_url)

        for id_string, download_url, manifest_url in forms:
            form_path = os.path.join(self.forms_path, id_string, f"{id_string}.xml")

            if not default_storage.exists(form_path):
                if not self._get_response(download_url):
                    self.logger.error("Failed to download xform %s.", download_url)
                    continue

                form_res = getattr(self, "_current_response")
                content = ContentFile(form_res.content.strip())
                default_storage.save(form_path, content)
            else:
                form_res = default_storage.open(form_path)
                content = form_res.read()

            self.logger.debug("Fetched %s.", download_url)

            if manifest_url:
                self.download_manifest(manifest_url, id_string)

            if include_instances:
                self.download_instances(id_string)
                self.logger.debug("Done downloading submissions for %s", id_string)

    @retry(NUM_RETRIES)
    def _get_response(self, url, params=None):
        """
        Downloads the url and sets self._current_response with the contents.
        """
        setattr(self, "_current_response", None)
        response = requests.get(
            url, auth=self.auth, params=params, timeout=DEFAULT_REQUEST_TIMEOUT
        )
        success = response.status_code == 200
        setattr(self, "_current_response", response)

        return success

    @retry(NUM_RETRIES)
    def _get_media_response(self, url):
        """
        Downloads the media file and sets self._current_response with the contents.
        """
        setattr(self, "_current_response", None)
        head_response = requests.head(
            url, auth=self.auth, timeout=DEFAULT_REQUEST_TIMEOUT
        )

        # S3 redirects, avoid using formhub digest on S3
        if head_response.status_code == 302:
            url = head_response.headers.get("location")

        response = requests.get(url, timeout=DEFAULT_REQUEST_TIMEOUT)
        success = response.status_code == 200
        setattr(self, "_current_response", response)

        return success

    def download_media_files(self, xml_doc, media_path):
        """Downloads media files from an ODK server."""
        for media_node in xml_doc.getElementsByTagName("mediaFile"):
            filename_node = media_node.getElementsByTagName("filename")
            url_node = media_node.getElementsByTagName("downloadUrl")
            if filename_node and url_node:
                filename = filename_node[0].childNodes[0].nodeValue
                path = os.path.join(media_path, filename)
                if default_storage.exists(path):
                    continue
                download_url = url_node[0].childNodes[0].nodeValue
                if self._get_media_response(download_url):
                    download_res = getattr(self, "_current_response")
                    media_content = ContentFile(download_res.content)
                    default_storage.save(path, media_content)
                    self.logger.debug("Fetched %s.", filename)
                else:
                    self.logger.error("Failed to fetch %s.", filename)

    # pylint: disable=too-many-locals
    def download_instances(self, form_id, cursor=0, num_entries=100):
        """Download the XML submissions."""
        self.logger.debug("Starting submissions download for %s", form_id)
        downloaded = self._get_response(
            self.submission_list_url,
            params={"formId": form_id, "numEntries": num_entries, "cursor": cursor},
        )
        if not downloaded:
            self.logger.error(
                "Fetching %s formId: %s, cursor: %s",
                self.submission_list_url,
                form_id,
                cursor,
            )
            return

        response = getattr(self, "_current_response")
        self.logger.debug(
            "Fetching %s formId: %s, cursor: %s",
            self.submission_list_url,
            form_id,
            cursor,
        )
        try:
            xml_doc = clean_and_parse_xml(response.content)
        except ExpatError:
            return

        instances = _get_instances_uuids(xml_doc)
        path = os.path.join(self.forms_path, form_id, "instances")

        for uuid in instances:
            self.logger.debug("Fetching %s %s submission", uuid, form_id)
            form_str = (
                "%(formId)s[@version=null and @uiVersion=null]/"
                "%(formId)s[@key=%(instanceId)s]"
                % {"formId": form_id, "instanceId": uuid}
            )
            instance_path = os.path.join(path, uuid.replace(":", ""), "submission.xml")
            if not default_storage.exists(instance_path):
                downloaded = self._get_response(
                    self.download_submission_url, params={"formId": form_str}
                )
                if downloaded:
                    instance_res = getattr(self, "_current_response")
                    content = instance_res.content.strip()
                    default_storage.save(instance_path, ContentFile(content))
                else:
                    continue
            else:
                instance_res = default_storage.open(instance_path)
                content = instance_res.read()

            try:
                instance_doc = clean_and_parse_xml(content)
            except ExpatError:
                continue

            media_path = os.path.join(path, uuid.replace(":", ""))
            self.download_media_files(instance_doc, media_path)
            self.logger.debug("Fetched %s %s submission", form_id, uuid)

        if xml_doc.getElementsByTagName("resumptionCursor"):
            rs_node = xml_doc.getElementsByTagName("resumptionCursor")[0]
            cursor = rs_node.childNodes[0].nodeValue

            if self.resumption_cursor != cursor:
                self.resumption_cursor = cursor
                self.download_instances(form_id, cursor)

    @transaction.atomic
    def _upload_xform(self, path, file_name):
        """Publishes the XForm XML to the XForm model."""
        xml_file = default_storage.open(path)
        xml_file.name = file_name
        k = PublishXForm(xml_file, self.user)

        return publish_form(k.publish_xform)

    def _upload_instance(self, xml_file, instance_dir_path, files):
        """
        Adds an xform submission to the Instance model.
        """
        xml_doc = clean_and_parse_xml(xml_file.read())
        xml = StringIO()
        de_node = xml_doc.documentElement
        for node in de_node.firstChild.childNodes:
            xml.write(node.toxml())
        new_xml_file = ContentFile(xml.getvalue().encode("utf-8"))
        new_xml_file.content_type = "text/xml"
        xml.close()
        attachments = []

        for attach in de_node.getElementsByTagName("mediaFile"):
            filename_node = attach.getElementsByTagName("filename")
            filename = filename_node[0].childNodes[0].nodeValue
            if filename in files:
                file_obj = default_storage.open(
                    os.path.join(instance_dir_path, filename)
                )
                mimetype, _encoding = mimetypes.guess_type(file_obj.name)
                media_obj = django_file(file_obj, "media_files[]", mimetype)
                attachments.append(media_obj)

        create_instance(self.user.username, new_xml_file, attachments)

    def _upload_instances(self, path):
        instances_count = 0
        dirs, _not_in_use = default_storage.listdir(path)

        for instance_dir in dirs:
            instance_dir_path = os.path.join(path, instance_dir)
            _dirs, files = default_storage.listdir(instance_dir_path)
            xml_file = None

            if "submission.xml" in files:
                file_obj = default_storage.open(
                    os.path.join(instance_dir_path, "submission.xml")
                )
                xml_file = file_obj

            if xml_file:
                try:
                    self._upload_instance(xml_file, instance_dir_path, files)
                except ExpatError:
                    continue
                # pylint: disable=broad-except
                except Exception as error:
                    # keep going despite some errors.
                    logging.exception(
                        (
                            "Ignoring exception, processing XML submission "
                            "raised exception: %s"
                        ),
                        str(error),
                    )
                else:
                    instances_count += 1

        return instances_count

    def push(self):
        """Publishes XForms and XForm submissions."""
        dirs, _files = default_storage.listdir(self.forms_path)
        for form_dir in dirs:
            dir_path = os.path.join(self.forms_path, form_dir)
            form_dirs, form_files = default_storage.listdir(dir_path)
            form_xml = f"{form_dir}.xml"
            if form_xml in form_files:
                form_xml_path = os.path.join(dir_path, form_xml)
                published_xform = self._upload_xform(form_xml_path, form_xml)
                if isinstance(published_xform, dict):
                    self.logger.error("Failed to publish %s", form_dir)
                else:
                    self.logger.debug("Successfully published %s", form_dir)
            if "instances" in form_dirs:
                self.logger.debug("Uploading instances")
                submission_count = self._upload_instances(
                    os.path.join(dir_path, "instances")
                )
                self.logger.debug(
                    "Published %d instances for %s", submission_count, form_dir
                )
