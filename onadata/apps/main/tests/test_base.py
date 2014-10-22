import base64
import os
import re
import socket
import urllib2
from tempfile import NamedTemporaryFile

from cStringIO import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.test.client import Client
from django_digest.test import Client as DigestClient
from django_digest.test import DigestAuth
from django.contrib.auth import authenticate
from django.utils import timezone

from rest_framework.test import APIRequestFactory

from onadata.apps.logger.models import XForm, Instance, Attachment
from onadata.apps.logger.views import submission
from onadata.apps.main.models import UserProfile


class TestBase(TransactionTestCase):

    surveys = ['transport_2011-07-25_19-05-49',
               'transport_2011-07-25_19-05-36',
               'transport_2011-07-25_19-06-01',
               'transport_2011-07-25_19-06-14']
    this_directory = os.path.dirname(__file__)

    def setUp(self):
        self.maxDiff = None
        self._create_user_and_login()
        self.base_url = 'http://testserver'
        self.factory = APIRequestFactory()

    def tearDown(self):
        # clear mongo db after each test
        settings.MONGO_DB.instances.drop()

    def _fixture_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'fixtures', *args)

    def _create_user(self, username, password):
        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.save()

        return user

    def _login(self, username, password):
        client = Client()
        assert client.login(username=username, password=password)
        return client

    def _logout(self, client=None):
        if not client:
            client = self.client
        client.logout()

    def _create_user_and_login(self, username="bob", password="bob"):
        self.login_username = username
        self.login_password = password
        self.user = self._create_user(username, password)

        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        profile.require_auth = False
        profile.save()

        self.client = self._login(username, password)
        self.anon = Client()

    def _publish_xls_file(self, path):
        if not path.startswith('/%s/' % self.user.username):
            path = os.path.join(self.this_directory, path)
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            return self.client.post('/%s/' % self.user.username, post_data)

    def _publish_xlsx_file(self):
        path = os.path.join(self.this_directory, 'fixtures', 'exp.xlsx')
        pre_count = XForm.objects.count()
        response = TestBase._publish_xls_file(self, path)
        # make sure publishing the survey worked
        self.assertEqual(response.status_code, 200)
        self.assertEqual(XForm.objects.count(), pre_count + 1)

    def _publish_xls_file_and_set_xform(self, path):
        count = XForm.objects.count()
        self.response = self._publish_xls_file(path)
        self.assertEqual(XForm.objects.count(), count + 1)
        self.xform = XForm.objects.order_by('pk').reverse()[0]

    def _share_form_data(self, id_string='transportation_2011_07_25'):
        xform = XForm.objects.get(id_string=id_string)
        xform.shared_data = True
        xform.save()

    def _publish_transportation_form(self):
        xls_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.xls")
        count = XForm.objects.count()
        TestBase._publish_xls_file(self, xls_path)
        self.assertEqual(XForm.objects.count(), count + 1)
        self.xform = XForm.objects.order_by('pk').reverse()[0]

    def _submit_transport_instance(self, survey_at=0):
        s = self.surveys[survey_at]
        self._make_submission(os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'))

    def _submit_transport_instance_w_uuid(self, name):
        self._make_submission(os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances_w_uuid', name, name + '.xml'))

    def _submit_transport_instance_w_attachment(self, survey_at=0):
        s = self.surveys[survey_at]
        media_file = "1335783522563.jpg"
        self._make_submission_w_attachment(os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'),
            os.path.join(self.this_directory, 'fixtures',
                         'transportation', 'instances', s, media_file))
        self.attachment = Attachment.objects.all().reverse()[0]
        self.attachment_media_file = self.attachment.media_file

    def _publish_transportation_form_and_submit_instance(self):
        self._publish_transportation_form()
        self._submit_transport_instance()

    def _make_submissions_gps(self):
        surveys = ['gps_1980-01-23_20-52-08',
                   'gps_1980-01-23_21-21-33', ]
        for survey in surveys:
            path = self._fixture_path('gps', 'instances', survey + '.xml')
            self._make_submission(path)

    def _make_submission(self, path, username=None, add_uuid=False,
                         forced_submission_time=None, auth=None, client=None):
        # store temporary file with dynamic uuid

        self.factory = APIRequestFactory()
        if auth is None:
            auth = DigestAuth('bob', 'bob')

        tmp_file = None

        if add_uuid:
            tmp_file = NamedTemporaryFile(delete=False)
            split_xml = None

            with open(path) as _file:
                split_xml = re.split(r'(<transport>)', _file.read())

            split_xml[1:1] = [
                '<formhub><uuid>%s</uuid></formhub>' % self.xform.uuid
            ]
            tmp_file.write(''.join(split_xml))
            path = tmp_file.name
            tmp_file.close()

        with open(path) as f:
            post_data = {'xml_submission_file': f}

            if username is None:
                username = self.user.username

            url_prefix = '%s/' % username if username else ''
            url = '/%ssubmission' % url_prefix

            request = self.factory.post(url, post_data)
            request.user = authenticate(username=auth.username,
                                        password=auth.password)

            self.response = submission(request, username=username)

            if auth and self.response.status_code == 401:
                request.META.update(auth(request.META, self.response))
                self.response = submission(request, username=username)

        if forced_submission_time:
            instance = Instance.objects.order_by('-pk').all()[0]
            instance.date_created = forced_submission_time
            instance.save()
            instance.parsed_instance.save()

        # remove temporary file if stored
        if add_uuid:
            os.unlink(tmp_file.name)

    def _make_submission_w_attachment(self, path, attachment_path):
        with open(path) as f:
            a = open(attachment_path)
            post_data = {'xml_submission_file': f, 'media_file': a}
            url = '/%s/submission' % self.user.username
            auth = DigestAuth('bob', 'bob')
            self.factory = APIRequestFactory()
            request = self.factory.post(url, post_data)
            request.user = authenticate(username='bob',
                                        password='bob')
            self.response = submission(request,
                                       username=self.user.username)

            if auth and self.response.status_code == 401:
                request.META.update(auth(request.META, self.response))
                self.response = submission(request,
                                           username=self.user.username)

    def _make_submissions(self, username=None, add_uuid=False,
                          should_store=True):
        """Make test fixture submissions to current xform.

        :param username: submit under this username, default None.
        :param add_uuid: add UUID to submission, default False.
        :param should_store: should submissions be save, default True.
        """

        paths = [os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'instances', s, s + '.xml') for s in self.surveys]
        pre_count = Instance.objects.count()

        for path in paths:
            self._make_submission(path, username, add_uuid)

        post_count = pre_count + len(self.surveys) if should_store\
            else pre_count
        self.assertEqual(Instance.objects.count(), post_count)
        self.assertEqual(self.xform.instances.count(), post_count)
        xform = XForm.objects.get(pk=self.xform.pk)
        self.assertEqual(xform.num_of_submissions, post_count)
        self.assertEqual(xform.user.profile.num_of_submissions, post_count)

    def _check_url(self, url, timeout=1):
        try:
            urllib2.urlopen(url, timeout=timeout)
            return True
        except (urllib2.URLError, socket.timeout):
            pass
        return False

    def _internet_on(self, url='http://74.125.113.99'):
        # default value is some google IP
        return self._check_url(url)

    def _set_auth_headers(self, username, password):
        return {
            'HTTP_AUTHORIZATION':
            'Basic ' + base64.b64encode('%s:%s' % (username, password)),
        }

    def _get_authenticated_client(
            self, url, username='bob', password='bob', extra={}):
        client = DigestClient()
        # request with no credentials
        req = client.get(url, {}, **extra)
        self.assertEqual(req.status_code, 401)
        # apply credentials
        client.set_authorization(username, password, 'Digest')
        return client

    def _get_response_content(self, response):
        contents = u''
        if response.streaming:
            actual_content = StringIO()
            for content in response.streaming_content:
                actual_content.write(content)
            contents = actual_content.getvalue()
            actual_content.close()
        else:
            contents = response.content
        return contents

    def _set_mock_time(self, mock_time):
        current_time = timezone.now()
        mock_time.return_value = current_time

    def _set_require_auth(self, auth=True):
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        profile.require_auth = auth
        profile.save()

    def _get_digest_client(self):
        self._set_require_auth(True)
        client = DigestClient()
        client.set_authorization('bob', 'bob', 'Digest')
        return client
