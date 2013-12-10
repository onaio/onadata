import os.path
import requests

from cStringIO import StringIO
from urlparse import urljoin
from httmock import urlmatch, HTTMock

from django.contrib.auth.models import AnonymousUser
from django.core.files.storage import get_storage_class
from django.core.urlresolvers import reverse
from django.test import RequestFactory
from django_digest.test import Client as DigestClient

from main.tests.test_base import MainTestCase
from main.views import profile

from odk_logger.models import Instance
from odk_logger.views import formList, download_xform

from utils.briefcase_client import BriefcaseClient

storage = get_storage_class()()


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


@urlmatch(netloc=r'(.*\.)?testserver$')
def instances_xml(url, request, **kwargs):
    response = requests.Response()
    client = DigestClient()
    client.set_authorization('bob', 'bob', 'Digest')
    res = client.get('%s?%s' % (url.path, url.query))
    if res.status_code == 302:
        res = client.get(res['Location'])
        content = StringIO()
        for chunk in res.streaming_content:
            content.write(chunk)
        response._content = content.getvalue()
        content.close()
        response.encoding = res.get('content-type')
    else:
        response._content = res.content
    response.status_code = 200
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
        with HTTMock(instances_xml):
            self.bc.download_instances(self.xform.id_string)
        instance_folder_path = os.path.join(
            'deno', 'briefcase', 'forms', self.xform.id_string, 'instances')
        self.assertTrue(storage.exists(instance_folder_path))
        instance = Instance.objects.all()[0]
        instance_path = os.path.join(
            instance_folder_path, 'uuid%s' % instance.uuid, 'submission.xml')
        self.assertTrue(storage.exists(instance_path))
        media_file = "1335783522563.jpg"
        media_path = os.path.join(
            instance_folder_path, 'uuid%s' % instance.uuid, media_file)
        self.assertTrue(storage.exists(media_path))
