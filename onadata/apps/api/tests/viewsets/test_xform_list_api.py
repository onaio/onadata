import os

from django.test import TransactionTestCase
from django_digest.test import DigestAuth

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_list_api import XFormListApi
from onadata.libs.permissions import ReadOnlyRole


class TestXFormListApi(TestAbstractViewSet, TransactionTestCase):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = XFormListApi.as_view({
            "get": "list"
        })
        self._publish_xls_form_to_project()

    def test_get_xform_list(self):
        request = self.factory.get('/')
        response = self.view(request)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'formList.xml')

        with open(path) as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_get_xform_list_other_user_with_no_role(self):
        request = self.factory.get('/')
        response = self.view(request)
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        self.assertFalse(
            ReadOnlyRole.user_has_role(alice_profile.user, self.xform)
        )

        auth = DigestAuth('alice', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        content = response.render().content
        self.assertNotIn(self.xform.id_string, content)
        self.assertEqual(
            content, '<?xml version="1.0" encoding="utf-8"?>\n<xforms '
            'xmlns="http://openrosa.org/xforms/xformsList"></xforms>')
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Content-Type'], 'text/xml; charset=utf-8')

    def test_get_xform_list_other_user_with_readonly_role(self):
        request = self.factory.get('/')
        response = self.view(request)
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        ReadOnlyRole.add(alice_profile.user, self.xform)

        self.assertTrue(
            ReadOnlyRole.user_has_role(alice_profile.user, self.xform)
        )

        auth = DigestAuth('alice', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'formList.xml')

        with open(path) as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_retrieve_xform_xml(self):
        self.view = XFormListApi.as_view({
            "get": "retrieve"
        })
        request = self.factory.head('/')
        response = self.view(request)
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'Transportation Form.xml')

        with open(path) as f:
            form_xml = f.read().strip()
            data = {"form_uuid": self.xform.uuid}
            content = response.render().content.strip()
            self.assertEqual(content, form_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')
