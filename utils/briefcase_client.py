import os
import requests
from requests.auth import HTTPDigestAuth
from urlparse import urljoin

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from odk_logger.xform_instance_parser import clean_and_parse_xml
from utils.logger_tools import publish_xml_form, publish_form


class BriefcaseClient(object):
    def __init__(self, url, username, password, user):
        self.url = url
        self.user = user
        self.auth = HTTPDigestAuth(username, password)
        self.form_list_url = urljoin(self.url, 'formList')
        self.submission_list_url = urljoin(self.url, 'view/submissionList')
        self.download_submission_url = urljoin(self.url,
                                               'view/downloadSubmission')
        self.forms_path = os.path.join(
            self.user.username, 'briefcase', 'forms')
        self.resumption_cursor = 0

    def download_xforms(self, include_instances=False):
        # fetch formList
        response = requests.get(self.form_list_url, auth=self.auth)
        xmlDoc = clean_and_parse_xml(response.content)
        forms = []
        for childNode in xmlDoc.childNodes:
            if childNode.nodeName == 'xforms':
                for xformNode in childNode.childNodes:
                    if xformNode.nodeName == 'xform':
                        form_id = xformNode.getElementsByTagName('formID')[0]
                        id_string = form_id.childNodes[0].nodeValue
                        d = xformNode.getElementsByTagName('downloadUrl')[0]
                        download_url = d.childNodes[0].nodeValue
                        m = xformNode.getElementsByTagName('manifestUrl')[0]
                        manifest_url = m.childNodes[0].nodeValue
                        forms.append((id_string, download_url, manifest_url))
        # download each xform
        if forms:
            for id_string, download_url, manifest_url in forms:
                form_path = os.path.join(
                    self.forms_path, id_string, '%s.xml' % id_string)
                form_res = requests.get(download_url, auth=self.auth)
                content = ContentFile(form_res.content.strip())
                default_storage.save(form_path, content)
                manifest_res = requests.get(manifest_url, auth=self.auth)
                manifest_doc = clean_and_parse_xml(manifest_res.content)
                manifest_path = os.path.join(
                    self.forms_path, id_string, 'form-media')
                self.download_media_files(manifest_doc, manifest_path)
                if include_instances:
                    self.download_instances(id_string)

    def download_media_files(self, xml_doc, media_path):
        for media_node in xml_doc.getElementsByTagName('mediaFile'):
            filename_node = media_node.getElementsByTagName('filename')
            url_node = media_node.getElementsByTagName('downloadUrl')
            if filename_node and url_node:
                filename = filename_node[0].childNodes[0].nodeValue
                download_url = url_node[0].childNodes[0].nodeValue
                download_res = requests.get(download_url, auth=self.auth)
                media_content = ContentFile(download_res.content)
                path = os.path.join(media_path, filename)
                default_storage.save(path, media_content)

    def download_instances(self, form_id, cursor=0, num_entries=100):
        response = requests.get(self.submission_list_url, auth=self.auth,
                                params={'formId': form_id,
                                        'numEntries': num_entries,
                                        'cursor': cursor})
        xml_doc = clean_and_parse_xml(response.content)
        instances = []
        for child_node in xml_doc.childNodes:
            if child_node.nodeName == 'idChunk':
                for id_node in child_node.getElementsByTagName('id'):
                    if id_node.childNodes:
                        instance_id = id_node.childNodes[0].nodeValue
                        instances.append(instance_id)
        path = os.path.join(self.forms_path, form_id, 'instances')
        for uuid in instances:
            form_str = u'%(formId)s[@version=null and @uiVersion=null]/'\
                u'%(formId)s[@key=%(instanceId)s]' % {
                    'formId': form_id,
                    'instanceId': uuid
                }
            instance_res = requests.get(self.download_submission_url,
                                        auth=self.auth,
                                        params={'formId': form_str})
            instance_path = os.path.join(path, uuid.replace(':', ''),
                                         'submission.xml')
            content = instance_res.content.strip()
            default_storage.save(instance_path, ContentFile(content))
            instance_doc = clean_and_parse_xml(content)
            media_path = os.path.join(path, uuid.replace(':', ''))
            self.download_media_files(instance_doc, media_path)
        if xml_doc.getElementsByTagName('resumptionCursor'):
            rs_node = xml_doc.getElementsByTagName('resumptionCursor')[0]
            cursor = rs_node.childNodes[0].nodeValue
            if self.resumption_cursor != cursor:
                self.resumption_cursor = cursor
                self.download_instances(form_id, cursor)

    def _upload_xform(self, path, file_name):
        class PublishXForm(object):
            def __init__(self, xml_file, user):
                self.xml_file = xml_file
                self.user = user

            def publish_xform(self):
                return publish_xml_form(self.xml_file, self.user)
        xml_file = default_storage.open(path)
        xml_file.name = file_name
        k = PublishXForm(xml_file, self.user)
        return publish_form(k.publish_xform)

    def _upload_instances(self, path):
        pass

    def push(self):
        dirs, files = default_storage.listdir(self.forms_path)
        for form_dir in dirs:
            dir_path = os.path.join(self.forms_path, form_dir)
            form_dirs, form_files = default_storage.listdir(dir_path)
            form_xml = '%s.xml' % form_dir
            if form_xml in form_files:
                form_xml_path = os.path.join(dir_path, form_xml)
                x = self._upload_xform(form_xml_path, form_xml)
                if isinstance(x, dict):
                    print "Failed to publish %s" % form_dir
                else:
                    print "Successfully published %s" % form_dir
            if 'instances' in form_dirs:
                self._upload_instances(os.path.join(dir_path, 'instances'))
