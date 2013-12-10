import os
import requests
from requests.auth import HTTPDigestAuth
from urlparse import urljoin

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from odk_logger.xform_instance_parser import clean_and_parse_xml


class BriefcaseClient(object):
    def __init__(self, url, username, password, user):
        self.url = url
        self.user = user
        self.auth = HTTPDigestAuth(username, password)
        self.form_list_url = urljoin(self.url, 'formList')
        self.submission_list_url = urljoin(self.url, 'view/submissionList')
        self.download_submission_url = urljoin(self.url,
                                               'view/downloadSubmission')

    def download_xforms(self):
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
                        forms.append((id_string, download_url))
        # download each xform
        if forms:
            path = os.path.join(self.user.username, 'briefcase', 'forms')
            for id_string, download_url in forms:
                form_path = os.path.join(path, id_string, '%s.xml' % id_string)
                form_res = requests.get(download_url, auth=self.auth)
                content = ContentFile(form_res.content.strip())
                default_storage.save(form_path, content)

    def download_instances(self, form_id):
        response = requests.get(self.submission_list_url,
                                params={'formId': form_id})
        xmlDoc = clean_and_parse_xml(response.content)
        instances = []
        for childNode in xmlDoc.childNodes:
            if childNode.nodeName == 'idChunk':
                for idNode in childNode.getElementsByTagName('id'):
                    if idNode.childNodes:
                        instance_id = idNode.childNodes[0].nodeValue
                        instances.append(instance_id)
        path = os.path.join(self.user.username, 'briefcase', 'forms',
                            form_id, 'instances')
        for uuid in instances:
            form_str = u'%(formId)s[@version=null and @uiVersion=null]/'\
                u'%(formId)s[@key=%(instanceId)s]' % {
                    'formId': form_id,
                    'instanceId': uuid
                }
            instance_res = requests.get(self.download_submission_url,
                                        params={'formId': form_str})
            instance_path = os.path.join(path, uuid.replace(':', ''),
                                         'submission.xml')
            content = instance_res.content.strip()
            default_storage.save(instance_path, ContentFile(content))
