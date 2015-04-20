import os
import shutil
import codecs

from django.core.urlresolvers import reverse
from django.core.files.storage import get_storage_class
from django_digest.test import DigestAuth
from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets import test_abstract_viewset
from onadata.apps.api.viewsets.briefcase_viewset import BriefcaseViewset
from onadata.apps.api.viewsets.xform_submission_viewset import XFormSubmissionViewSet
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet

NUM_INSTANCES = 4
storage = get_storage_class()()


def ordered_instances(xform):
    return Instance.objects.filter(xform=xform).order_by('id')


class TestBriefcaseViewSet(test_abstract_viewset.TestAbstractViewSet):

    def setUp(self):
        super(test_abstract_viewset.TestAbstractViewSet, self).setUp()
        self.factory = APIRequestFactory()
        self._login_user_and_profile()
        self.login_username = 'bob'
        self.login_password = 'bobbob'
        self.maxDiff = None
        self.form_def_path = os.path.join(
            self.main_directory, 'fixtures', 'transportation',
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

    def _publish_xml_form(self, auth=None):
        view = BriefcaseViewset.as_view({'post': 'create'})
        count = XForm.objects.count()

        with codecs.open(self.form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            auth = auth or DigestAuth(self.login_username, self.login_password)
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)

            self.assertEqual(XForm.objects.count(), count + 1)
            self.assertContains(
                response, "successfully published.", status_code=201)
        self.xform = XForm.objects.order_by('pk').reverse()[0]

    def test_view_submission_list(self):
        view = BriefcaseViewset.as_view({'get': 'list'})
        self._publish_xml_form()
        self._make_submissions()
        request = self.factory.get(
            self._submission_list_url,
            data={'formId': self.xform.id_string})
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'view', 'submissionList.xml')
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, 'rb', encoding='utf-8') as f:
            expected_submission_list = f.read()
            expected_submission_list = \
                expected_submission_list.replace(
                    '{{resumptionCursor}}', '%s' % last_index)
            self.assertContains(response, expected_submission_list)

    def test_view_submission_list_w_deleted_submission(self):
        view = BriefcaseViewset.as_view({'get': 'list'})
        self._publish_xml_form()
        self._make_submissions()
        uuid = 'f3d8dc65-91a6-4d0f-9e97-802128083390'
        Instance.objects.filter(uuid=uuid).order_by('id').delete()
        request = self.factory.get(
            self._submission_list_url,
            data={'formId': self.xform.id_string})
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        submission_list_path = os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'view', 'submissionList-4.xml')
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES - 1)

        last_index = instances[instances.count() - 1].pk
        with codecs.open(submission_list_path, 'rb', encoding='utf-8') as f:
            expected_submission_list = f.read()
            expected_submission_list = \
                expected_submission_list.replace(
                    '{{resumptionCursor}}', '%s' % last_index)
            self.assertContains(response, expected_submission_list)

        view = BriefcaseViewset.as_view({'get': 'retrieve'})
        formId = u'%(formId)s[@version=null and @uiVersion=null]/' \
                 u'%(formId)s[@key=uuid:%(instanceId)s]' % {
                     'formId': self.xform.id_string,
                     'instanceId': uuid}
        params = {'formId': formId}
        request = self.factory.get(
            self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth(self.login_username, self.login_password)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertTrue(response.status_code, 404)

    def test_view_submission_list_OtherUser(self):
        view = BriefcaseViewset.as_view({'get': 'list'})
        self._publish_xml_form()
        self._make_submissions()
        # alice cannot view bob's submissionList
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._create_user_profile(alice_data)
        auth = DigestAuth('alice', 'bobbob')
        request = self.factory.get(
            self._submission_list_url,
            data={'formId': self.xform.id_string})
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 404)

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

        view = BriefcaseViewset.as_view({'get': 'list'})
        self._publish_xml_form()
        self._make_submissions()
        params = {'formId': self.xform.id_string}
        params['numEntries'] = 2
        instances = ordered_instances(self.xform)

        self.assertEqual(instances.count(), NUM_INSTANCES)

        last_index = instances[:2][1].pk
        last_expected_submission_list = ""
        for index in range(1, 5):
            auth = DigestAuth(self.login_username, self.login_password)
            request = self.factory.get(
                self._submission_list_url,
                data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 200)
            if index > 2:
                last_index = get_last_index(self.xform, last_index)
            filename = 'submissionList-%s.xml' % index
            if index == 4:
                self.assertContains(response, last_expected_submission_list)
                continue
            # set cursor for second request
            params['cursor'] = last_index
            submission_list_path = os.path.join(
                self.main_directory, 'fixtures', 'transportation',
                'view', filename)
            with codecs.open(submission_list_path, encoding='utf-8') as f:
                expected_submission_list = f.read()
                last_expected_submission_list = expected_submission_list = \
                    expected_submission_list.replace(
                        '{{resumptionCursor}}', '%s' % last_index)
                self.assertContains(response, expected_submission_list)
            last_index += 2

    def test_view_downloadSubmission(self):
        view = BriefcaseViewset.as_view({'get': 'retrieve'})
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
        auth = DigestAuth(self.login_username, self.login_password)
        request = self.factory.get(
            self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        text = "uuid:%s" % instanceId
        download_submission_path = os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'view', 'downloadSubmission.xml')
        with codecs.open(download_submission_path, encoding='utf-8') as f:
            text = f.read()
            text = text.replace(u'{{submissionDate}}',
                                instance.date_created.isoformat())
            self.assertContains(response, instanceId, status_code=200)
            self.assertMultiLineEqual(response.content, text)

    def test_view_downloadSubmission_OtherUser(self):
        view = BriefcaseViewset.as_view({'get': 'retrieve'})
        self._publish_xml_form()
        self.maxDiff = None
        self._submit_transport_instance_w_attachment()
        instanceId = u'5b2cc313-fc09-437e-8149-fcd32f695d41'
        formId = u'%(formId)s[@version=null and @uiVersion=null]/' \
                 u'%(formId)s[@key=uuid:%(instanceId)s]' % {
                     'formId': self.xform.id_string,
                     'instanceId': instanceId}
        params = {'formId': formId}
        # alice cannot view bob's downloadSubmission
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._create_user_profile(alice_data)
        auth = DigestAuth('alice', 'bobbob')
        request = self.factory.get(
            self._download_submission_url, data=params)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 404)

    def test_publish_xml_form_OtherUser(self):
        view = BriefcaseViewset.as_view({'post': 'create'})
        # deno cannot publish form to bob's account
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._create_user_profile(alice_data)
        count = XForm.objects.count()

        with codecs.open(self.form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            auth = DigestAuth('alice', 'bobbob')
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertNotEqual(XForm.objects.count(), count + 1)
            self.assertEqual(response.status_code, 403)

    def test_publish_xml_form_where_filename_is_not_id_string(self):
        view = BriefcaseViewset.as_view({'post': 'create'})
        form_def_path = os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'Transportation Form.xml')
        count = XForm.objects.count()
        with codecs.open(form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            auth = DigestAuth(self.login_username, self.login_password)
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertEqual(XForm.objects.count(), count + 1)
            self.assertContains(
                response, "successfully published.", status_code=201)

    def test_form_upload(self):
        view = BriefcaseViewset.as_view({'post': 'create'})
        self._publish_xml_form()

        with codecs.open(self.form_def_path, encoding='utf-8') as f:
            params = {'form_def_file': f, 'dataFile': ''}
            auth = DigestAuth(self.login_username, self.login_password)
            request = self.factory.post(self._form_upload_url, data=params)
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 401)
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.data,
                {'message': u'Form with this id or SMS-keyword already exists.'
                 }
            )

    def test_upload_head_request(self):
        view = BriefcaseViewset.as_view({'head': 'create'})

        auth = DigestAuth(self.login_username, self.login_password)
        request = self.factory.head(self._form_upload_url)
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        request.META.update(auth(request.META, response))
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))

    def test_submission_with_instance_id_on_root_node(self):
        view = XFormSubmissionViewSet.as_view({'post': 'create'})
        self._publish_xml_form()
        message = u"Successful submission."
        instanceId = u'5b2cc313-fc09-437e-8149-fcd32f695d41'
        self.assertRaises(
            Instance.DoesNotExist, Instance.objects.get, uuid=instanceId)
        submission_path = os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'view', 'submission.xml')
        count = Instance.objects.count()
        with codecs.open(submission_path, encoding='utf-8') as f:
            post_data = {'xml_submission_file': f}
            request = self.factory.post(self._submission_list_url, post_data)
            response = view(request)
            self.assertEqual(response.status_code, 401)
            auth = DigestAuth('bob', 'bobbob')
            request.META.update(auth(request.META, response))
            response = view(request, username=self.user.username)
            self.assertContains(response, message, status_code=201)
            self.assertContains(response, instanceId, status_code=201)
            self.assertEqual(Instance.objects.count(), count + 1)

    def test_form_export_with_no_xlsform_returns_200(self):
        self._publish_xml_form()
        self.view = XFormViewSet.as_view({'get': 'retrieve'})

        xform = XForm.objects.get(id_string="transportation_2011_07_25")
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=xform.pk, format='csv')

        self.assertEqual(response.status_code, 200)

        self.view = XFormViewSet.as_view({'get': 'form'})
        response = self.view(request, pk=xform.pk, format='xls')
        self.assertEqual(response.status_code, 404)

    def tearDown(self):
        # remove media files
        if self.user:
            if storage.exists(self.user.username):
                shutil.rmtree(storage.path(self.user.username))
