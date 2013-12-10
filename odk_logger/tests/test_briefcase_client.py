import os.path
import requests

from urlparse import urljoin
from httmock import urlmatch, HTTMock

from django.contrib.auth.models import AnonymousUser
from django.core.files.storage import get_storage_class
from django.core.urlresolvers import reverse
from django.test import RequestFactory

from main.tests.test_base import MainTestCase
from main.views import profile

from odk_logger.views import formList, download_xform

from utils.briefcase_client import BriefcaseClient


@urlmatch(netloc=r'(.*\.)?testserver$')
def form_list_xml(url, request, **kwargs):
    factory = RequestFactory()
    req = factory.get(url.path)
    req.user = AnonymousUser()
    id_string = 'transportation_2011_07_25'
    if url.path.endswith('formList.xml'):
        res = formList(req, username='bob')
    elif url.path.endswith('form.xml'):
        res = download_xform(req, username='bob', id_string=id_string)
    else:
        res = formList(req, username='bob')
    response = requests.Response()
    response.status_code = 200
    response._content = res.content
    return response


class TestBriefcaseClient(MainTestCase):

    def setUp(self):
        MainTestCase.setUp(self)
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        url = urljoin(
            self.base_url,
            reverse(profile, kwargs={'username': self.user.username})
        )
        self._logout()
        self._create_user_and_login('deno', 'deno')
        self.bc = BriefcaseClient(
            username='bob', password='bob',
            url=url,
            user=self.user
        )

    def test_download_xform_xml(self):
        """
        Download xform via briefcase api
        """
        # check that [user]/briefcase/forms folder is created for user deno
        # check that [user]/briefcase/forms/[id_string].xml is created
        with HTTMock(form_list_xml):
            self.bc.download_xforms()
        storage = get_storage_class()()
        forms_folder_path = os.path.join(
            'deno', 'briefcase', 'forms', self.xform.id_string)
        self.assertTrue(storage.exists(forms_folder_path))
        forms_path = os.path.join(forms_folder_path,
                                  '%s.xml' % self.xform.id_string)
        self.assertTrue(storage.exists(forms_path))

    def test_download_form_media(self):
        """
        Download media via briefcase api
        """
        # check that [user]/briefcase/forms/[id_string]-media is created
        # check that media file is save in [id_string]-media
        pass

    def test_download_instance(self):
        """
        Download instance xml
        """
        # check that [user]/briefcase/forms/instances is created
        # check that instances/[uuid]/submission.xml is created
        pass

    def test_download_instance_with_attachment(self):
        """
        Download instance xml and attachments
        """
        # check that instances/[uuid]/[media_file.ext] is created
        pass
