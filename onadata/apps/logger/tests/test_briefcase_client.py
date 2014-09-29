import shutil
import os.path
import requests

from cStringIO import StringIO
from urlparse import urljoin
from httmock import urlmatch, HTTMock

from django.contrib.auth import authenticate
from django.core.files.storage import get_storage_class
from django.core.files.uploadedfile import UploadedFile
from django.core.urlresolvers import reverse
from django.test import RequestFactory
from django_digest.test import Client as DigestClient

from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import profile, download_media_data
from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.views import formList, download_xform, xformsManifest
from onadata.libs.utils.briefcase_client import BriefcaseClient

storage = get_storage_class()()


@urlmatch(netloc=r'(.*\.)?testserver$')
def form_list_xml(url, request, **kwargs):
    response = requests.Response()
    factory = RequestFactory()
    req = factory.get(url.path)
    req.user = authenticate(username='bob', password='bob')
    req.user.profile.require_auth = False
    req.user.profile.save()
    id_string = 'transportation_2011_07_25'
    if url.path.endswith('formList'):
        res = formList(req, username='bob')
    elif url.path.endswith('form.xml'):
        res = download_xform(req, username='bob', id_string=id_string)
    elif url.path.find('xformsManifest') > -1:
        res = xformsManifest(req, username='bob', id_string=id_string)
    elif url.path.find('formid-media') > -1:
        data_id = url.path[url.path.rfind('/') + 1:]
        res = download_media_data(
            req, username='bob', id_string=id_string, data_id=data_id)
        response._content = get_streaming_content(res)
    else:
        res = formList(req, username='bob')
    response.status_code = 200
    if not response._content:
        response._content = res.content
    return response


def get_streaming_content(res):
    tmp = StringIO()
    for chunk in res.streaming_content:
        tmp.write(chunk)
    content = tmp.getvalue()
    tmp.close()
    return content


@urlmatch(netloc=r'(.*\.)?testserver$')
def instances_xml(url, request, **kwargs):
    response = requests.Response()
    client = DigestClient()
    client.set_authorization('bob', 'bob', 'Digest')
    res = client.get('%s?%s' % (url.path, url.query))
    if res.status_code == 302:
        res = client.get(res['Location'])
        response.encoding = res.get('content-type')
        response._content = get_streaming_content(res)
    else:
        response._content = res.content
    response.status_code = 200
    return response


class TestBriefcaseClient(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        src = os.path.join(self.this_directory, "fixtures",
                           "transportation", "screenshot.png")
        uf = UploadedFile(file=open(src), content_type='image/png')
        count = MetaData.objects.count()
        MetaData.media_upload(self.xform, uf)
        self.assertEqual(MetaData.objects.count(), count + 1)
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
        with HTTMock(form_list_xml):
            self.bc.download_xforms()
        forms_folder_path = os.path.join(
            'deno', 'briefcase', 'forms', self.xform.id_string)
        self.assertTrue(storage.exists(forms_folder_path))
        forms_path = os.path.join(forms_folder_path,
                                  '%s.xml' % self.xform.id_string)
        self.assertTrue(storage.exists(forms_path))
        form_media_path = os.path.join(forms_folder_path, 'form-media')
        self.assertTrue(storage.exists(form_media_path))
        media_path = os.path.join(form_media_path, 'screenshot.png')
        self.assertTrue(storage.exists(media_path))

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

    def test_push(self):
        with HTTMock(form_list_xml):
            self.bc.download_xforms()
        with HTTMock(instances_xml):
            self.bc.download_instances(self.xform.id_string)
        XForm.objects.all().delete()
        xforms = XForm.objects.filter(
            user=self.user, id_string=self.xform.id_string)
        self.assertTrue(xforms.count() == 0)
        instances = Instance.objects.filter(
            xform__user=self.user, xform__id_string=self.xform.id_string)
        self.assertTrue(instances.count() == 0)
        self.bc.push()
        xforms = XForm.objects.filter(
            user=self.user, id_string=self.xform.id_string)
        self.assertTrue(xforms.count() == 1)
        instances = Instance.objects.filter(
            xform__user=self.user, xform__id_string=self.xform.id_string)
        self.assertTrue(instances.count() == 1)

    def tearDown(self):
        # remove media files
        for username in ['bob', 'deno']:
            if storage.exists(username):
                shutil.rmtree(storage.path(username))
