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
        self.form_list_url = urljoin(self.url, 'formList.xml')

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
            if not default_storage.exists(path):
                pass
            for id_string, download_url in forms:
                form_path = os.path.join(path, id_string, '%s.xml' % id_string)
                form_res = requests.get(download_url, auth=self.auth)
                default_storage.save(form_path, ContentFile(form_res.content))
