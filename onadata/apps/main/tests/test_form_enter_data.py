import os
import re
from time import time
from future.moves.urllib.parse import urlparse
from past.builtins import basestring

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.urlresolvers import reverse
from django.core.validators import URLValidator
from django.test import RequestFactory

import requests
from httmock import HTTMock, urlmatch
from nose import SkipTest

from onadata.apps.logger.views import enter_data
from onadata.apps.main.models import MetaData
from onadata.apps.main.views import qrcode, set_perm, show
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.viewer_tools import enketo_url


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"url": "https://hmh2a.enketo.ona.io"}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock_http(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"url": "http://enketo.ona.io/_/#abcd"}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_error_mock(url, request):
    response = requests.Response()
    response.status_code = 400
    response._content = '{"message": ' \
                        '"no account exists for this OpenRosa server"}'
    return response


class TestFormEnterData(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()
        self.perm_url = reverse(set_perm, kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        self.show_url = reverse(show, kwargs={'uuid': self.xform.uuid})
        self.url = reverse(enter_data, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })

    def _running_enketo(self, check_url=False):
        if hasattr(settings, 'ENKETO_URL') and \
                (not check_url or self._check_url(settings.ENKETO_URL)):
            return True
        return False

    def test_enketo_remote_server(self):
        if not self._running_enketo():
            raise SkipTest
        with HTTMock(enketo_mock):
            server_url = 'https://testserver.com/bob'
            form_id = "test_%s" % re.sub(re.compile("\."), "_", str(time()))
            url = enketo_url(server_url, form_id)
            self.assertIsInstance(url, basestring)
            self.assertIsNone(URLValidator()(url))

    def test_enketo_url_with_http_protocol_on_formlist(self):
        if not self._running_enketo():
            raise SkipTest
        with HTTMock(enketo_mock_http):
            server_url = 'http://testserver.com/bob'
            form_id = "test_%s" % re.sub(re.compile("\."), "_", str(time()))
            url = enketo_url(server_url, form_id)
            self.assertIn('http:', url)
            self.assertIsInstance(url, basestring)
            self.assertIsNone(URLValidator()(url))

    def _get_grcode_view_response(self):
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        response = qrcode(
            request, self.user.username, self.xform.id_string)

        return response

    def test_qrcode_view(self):
        with HTTMock(enketo_mock):
            response = self._get_grcode_view_response()
            qrfile = os.path.join(
                self.this_directory, 'fixtures', 'qrcode.response')
            with open(qrfile, 'r') as f:
                data = f.read()
                self.assertContains(response, data.strip(), status_code=200)

    def test_qrcode_view_with_enketo_error(self):
        with HTTMock(enketo_error_mock):
            response = self._get_grcode_view_response()
            self.assertEqual(response.status_code, 400)

    def test_enter_data_redir(self):
        if not self._running_enketo():
            raise SkipTest
        with HTTMock(enketo_mock):
            factory = RequestFactory()
            request = factory.get('/')
            request.user = self.user
            response = enter_data(
                request, self.user.username, self.xform.id_string)
            # make sure response redirect to an enketo site
            enketo_base_url = urlparse(settings.ENKETO_URL).netloc
            redirected_base_url = urlparse(response['Location']).netloc
            # TODO: checking if the form is valid on enketo side
            self.assertIn(enketo_base_url, redirected_base_url)
            self.assertEqual(response.status_code, 302)

    def test_enter_data_no_permission(self):
        response = self.anon.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_public_with_link_to_share_toggle_on(self):
        # sharing behavior as of 09/13/2012:
        # it requires both data_share and form_share both turned on
        # in order to grant anon access to form uploading
        # TODO: findout 'for_user': 'all' and what it means
        response = self.client.post(self.perm_url, {'for_user': 'all',
                                    'perm_type': 'link'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MetaData.public_link(self.xform), True)
        # toggle shared on
        self.xform.shared = True
        self.xform.shared_data = True
        self.xform.save()
        response = self.anon.get(self.show_url)
        self.assertEqual(response.status_code, 302)
        if not self._running_enketo():
            raise SkipTest
        with HTTMock(enketo_mock):
            factory = RequestFactory()
            request = factory.get('/')
            request.user = AnonymousUser()
            response = enter_data(
                request, self.user.username, self.xform.id_string)
            self.assertEqual(response.status_code, 302)

    def test_enter_data_non_existent_user(self):
        url = reverse(enter_data, kwargs={
            'username': 'nonexistentuser',
            'id_string': self.xform.id_string
        })
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 404)

    def test_enter_data_with_unavailable_id_string(self):
        url = reverse(enter_data, kwargs={
            'username': self.user,
            'id_string': 'random_id_string'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
