import os
import shutil
import codecs

from django.core.urlresolvers import reverse
from django.core.files.storage import get_storage_class
from django_digest.test import DigestAuth
from rest_framework.test import APIRequestFactory
from django.contrib.auth import authenticate

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.views import view_submission_list
from onadata.apps.logger.views import view_download_submission
from onadata.apps.logger.views import form_upload
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.logger.views import submission

NUM_INSTANCES = 4
storage = get_storage_class()()


def ordered_instances(xform):
    return Instance.objects.filter(xform=xform).order_by('id')


class TestBriefcaseAPI(TestBase):

    def setUp(self):
        super(TestBase, self).setUp()
        self.factory = APIRequestFactory()
        self._create_user_and_login()
        self._logout()
        self.form_def_path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'transportation.xml')
        self._submission_list_url = reverse(
            'view-submission-list', kwargs={'username': self.user.username})
        self._submission_url = reverse(
            'submissions', kwargs={'username': self.user.username})
        self._download_submission_url = reverse(
            'view-download-submission',
            kwargs={'username': self.user.username})
        self._form_upload_url = reverse(
            'form-upload', kwargs={'username': self.user.username})

    def test_view_submission_list(self):
        self._publish_xml_form()
        self._make_submissions()
        params = {'formId': self.xform.id_string}
        request = self.factory.get(self._submission_list_url, params)
        response = view_submission_list(request, self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view_submission_list(request, self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'view', 'submissionList.xml')
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, 'rb', encoding='utf-8') as f:
            expected_submission_list = f.read()
            expected_submission_list = \
                expected_submission_list.replace(
                    '{{resumptionCursor}}', '%s' % last_index)
            self.assertEqual(response.content, expected_submission_list)

    def test_view_submission_list_w_deleted_submission(self):
        self._publish_xml_form()
        self._make_submissions()
        uuid = 'f3d8dc65-91a6-4d0f-9e97-802128083390'
        Instance.objects.filter(uuid=uuid).order_by('id').delete()
        params = {'formId': self.xform.id_string}
        request = self.factory.get(self._submission_list_url, params)
        response = view_submission_list(request, self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view_submission_list(request, self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'view', 'submissionList-4.xml')
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES - 1)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, 'rb', encoding='utf-8') as f:
            expected_submission_list = f.read()
            expected_submission_list = \
                expected_submission_list.replace(
                    '{{resumptionCursor}}', '%s' % last_index)
            self.assertEqual(response.content, expected_submission_list)

        formId = u'%(formId)s[@version=null and @uiVersion=null]/' \
                 u'%(formId)s[@key=uuid:%(instanceId)s]' % {
                     'formId': self.xform.id_string,
                     'instanceId': uuid}
        params = {'formId': formId}
        response = self.client.get(self._download_submission_url, data=params)
        self.assertTrue(response.status_code, 404)

    def test_view_submission_list_OtherUser(self):
        self._publish_xml_form()
        self._make_submissions()
        params = {'formId': self.xform.id_string}
        # deno cannot view bob's submissionList
        self._create_user('deno', 'deno')
        request = self.factory.get(self._submission_list_url, params)
        response = view_submission_list(request, self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('deno', 'deno')
        request.META.update(auth(request.META, response))
        response = view_submission_list(request, self.user.username)
        self.assertEqual(response.status_code, 403)

    def test_view_submission_list_num_entries(self):
        def get_last_index(xform, last_index=None):
            instances = ordered_instances(xform)
            if not last_index and instances.count():
                return instances[instances.count() - 1].pk
            elif last_index:
                instances = instances.filter(pk__gt=last_index)
                if instances.count():
                    return instances[instances.count() - 1].pk
                else:
                    return get_last_index(xform)
            return 0

        self._publish_xml_form()
        self._make_submissions()
        params = {'formId': self.xform.id_string}
        params['numEntries'] = 2
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[:2][1].pk
        last_expected_submission_list = ""
        for index in range(1, 5):
            request = self.factory.get(self._submission_list_url, params)
            response = view_submission_list(request, self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth(self.login_username, self.login_password)
            request.META.update(auth(request.META, response))
            response = view_submission_list(request, self.user.username)
            self.assertEqual(response.status_code, 200)

            if index > 2:
                last_index = get_last_index(self.xform, last_index)
            filename = 'submissionList-%s.xml' % index

            if index == 4:
                self.assertEqual(
                    response.content, last_expected_submission_list)
                continue
            # set cursor for second request
            params['cursor'] = last_index
            submission_list_path = os.path.join(
                self.this_directory, 'fixtures', 'transportation',
                'view', filename)
            with codecs.open(submission_list_path, encoding='utf-8') as f:
                expected_submission_list = f.read()
                last_expected_submission_list = expected_submission_list = \
                    expected_submission_list.replace(
                        '{{resumptionCursor}}', '%s' % last_index)
                self.assertEqual(response.content, expected_submission_list)
            last_index += 2

    def test_view_downloadSubmission(self):
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = u'5b2cc313-fc09-437e-8149-fcd32f695d41'
        instance = Instance.objects.get(uuid=instanceId)
        formId = u'%(formId)s[@version=null and @uiVersion=null]/' \
                 u'%(formId)s[@key=uuid:%(instanceId)s]' % {
                     'formId': self.xform.id_string,
                     'instanceId': instanceId}
        params = {'formId': formId}
        request = self.factory.get(self._download_submission_url, params)
        response = view_download_submission(request, self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view_download_submission(request, self.user.username)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'view', 'downloadSubmission.xml')
        with codecs.open(download_submission_path, encoding='utf-8') as f:
            text = f.read()
            text = text.replace(u'{{submissionDate}}',
                                instance.date_created.isoformat())
            self.assertContains(response, instanceId, status_code=200)
            self.assertMultiLineEqual(response.content, text)

    def test_view_downloadSubmission_OtherUser(self):
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = u'5b2cc313-fc09-437e-8149-fcd32f695d41'
        formId = u'%(formId)s[@version=null and @uiVersion=null]/' \
                 u'%(formId)s[@key=uuid:%(instanceId)s]' % {
                     'formId': self.xform.id_string,
                     'instanceId': instanceId}
        params = {'formId': formId}
        # deno cannot view bob's downloadSubmission
        self._create_user('deno', 'deno')
        request = self.factory.get(self._download_submission_url, params)
        response = view_download_submission(request, self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('deno', 'deno')
        request.META.update(auth(request.META, response))
        response = view_download_submission(request, self.user.username)
        self.assertEqual(response.status_code, 403)

    def test_publish_xml_form_OtherUser(self):
        # deno cannot publish form to bob's account
        self._create_user('deno', 'deno')
        count = XForm.objects.count()

        with codecs.open(self.form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            request = self.factory.post(self._form_upload_url, params)
            response = form_upload(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth('deno', 'deno')
            request.META.update(auth(request.META, response))
            response = form_upload(request, username=self.user.username)
            self.assertNotEqual(XForm.objects.count(), count + 1)
            self.assertEqual(response.status_code, 403)

    def test_publish_xml_form_where_filename_is_not_id_string(self):
        form_def_path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'Transportation Form.xml')
        count = XForm.objects.count()
        with codecs.open(form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            request = self.factory.post(self._form_upload_url, params)
            response = form_upload(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth(self.login_username, self.login_password)
            request.META.update(auth(request.META, response))
            response = form_upload(request, username=self.user.username)
            self.assertContains(
                response, "successfully published.", status_code=201)
            self.assertEqual(XForm.objects.count(), count + 1)

    def _publish_xml_form(self):
        count = XForm.objects.count()
        with codecs.open(self.form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            request = self.factory.post(self._form_upload_url, params)
            response = form_upload(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth(self.login_username, self.login_password)
            request.META.update(auth(request.META, response))
            response = form_upload(request, username=self.user.username)
            self.assertContains(
                response, "successfully published.", status_code=201)
            self.assertEqual(XForm.objects.count(), count + 1)
        self.xform = XForm.objects.order_by('pk').reverse()[0]

    def test_form_upload(self):
        self._publish_xml_form()
        with codecs.open(self.form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            request = self.factory.post(self._form_upload_url, params)
            response = form_upload(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth(self.login_username, self.login_password)
            request.META.update(auth(request.META, response))
            response = form_upload(request, username=self.user.username)
            self.assertContains(
                response,
                u'Form with this id or SMS-keyword already exists',
                status_code=400)

    def test_submission_with_instance_id_on_root_node(self):
        self._publish_xml_form()
        message = u"Successful submission."
        instanceId = u'5b2cc313-fc09-437e-8149-fcd32f695d41'
        self.assertRaises(
            Instance.DoesNotExist, Instance.objects.get, uuid=instanceId)
        submission_path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'view', 'submission.xml')
        count = Instance.objects.count()
        with codecs.open(submission_path, encoding='utf-8') as f:
            post_data = {'xml_submission_file': f}
            self.factory = APIRequestFactory()
            request = self.factory.post(self._submission_url, post_data)
            request.user = authenticate(username='bob',
                                        password='bob')
            response = submission(request, username=self.user.username)
            self.assertContains(response, message, status_code=201)
            self.assertContains(response, instanceId, status_code=201)
            self.assertEqual(Instance.objects.count(), count + 1)

    def tearDown(self):
        # remove media files
        if self.user:
            if storage.exists(self.user.username):
                shutil.rmtree(storage.path(self.user.username))
