import os

from xml.dom import minidom

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django_digest.test import DigestAuth

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.views import formList
from onadata.libs.permissions import DataEntryRole

class TestFormList(TestBase):
    def setUp(self):
        super(TestFormList, self).setUp()
        self.factory = RequestFactory()

    def test_returns_200_for_owner(self):
        self._set_require_auth()
        request = self.factory.get('/')
        auth = DigestAuth('bob', 'bob')
        response = formList(request, self.user.username)
        request.META.update(auth(request.META, response))
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_return_401_for_anon_when_require_auth_true(self):
        self._set_require_auth()
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 401)

    def test_returns_200_for_authenticated_non_owner(self):
        self._set_require_auth()
        credentials = ('alice', 'alice',)
        self._create_user(*credentials)
        auth = DigestAuth('alice', 'alice')
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        request.META.update(auth(request.META, response))
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_show_for_anon_when_require_auth_false(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()
        response = formList(request, self.user.username)
        self.assertEquals(response.status_code, 200)

    def test_data_entry_can_see_shared_forms(self):
        self._publish_transportation_form_and_submit_instance()
        path = os.path.join(self.this_directory, 'fixtures', 'exp_line_break.xlsx')
        self._publish_xls_file(path)

        credentials = ('alice', 'alice',)
        self._create_user_and_login(*credentials)
        DataEntryRole.add(self.user, self.xform)

        self._publish_xlsx_file()
        request = self.factory.get('/')
        request.user = self.user
        response = formList(request, self.user.username)

        self.assertEqual(response.status_code, 200)

        xmldoc = minidom.parseString(response.content)
        self.assertEquals(2, len(xmldoc.getElementsByTagName('xform')))

    def test_return_form_with_require_auth_false_for_anon(self):
        self._set_require_auth()
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 401)