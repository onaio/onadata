import os
from hashlib import md5

from builtins import open
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TransactionTestCase
from django_digest.test import Client as DigestClient
from django_digest.test import DigestAuth
from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_list_viewset import (
    PreviewXFormListViewSet, XFormListViewSet)
from onadata.apps.main.models import MetaData
from onadata.libs.permissions import DataEntryRole, ReadOnlyRole, OwnerRole


class TestXFormListViewSet(TestAbstractViewSet, TransactionTestCase):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = XFormListViewSet.as_view({"get": "list"})
        self._publish_xls_form_to_project()

    def test_get_xform_list(self):
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')
        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_get_xform_list_xform_pk_filter_anon(self):
        """
        Test formList xform_pk filter for anonymous user.
        """
        request = self.factory.get('/')
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk + 10000)
        self.assertEqual(response.status_code, 404)

        # existing form is in result when xform_pk filter is in use.
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')

        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_get_xform_list_form_id_filter(self):
        """
        Test formList formID filter
        """
        # Test unrecognized formID
        request = self.factory.get('/', {'formID': 'unrecognizedID'})
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # Test a valid formID
        request = self.factory.get('/', {'formID': self.xform.id_string})
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')

        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)

    def test_form_id_filter_for_require_auth_account(self):
        """
        Test formList formID filter for account that requires authentication
        """
        # Bob submit forms
        xls_path = os.path.join(settings.PROJECT_ROOT, "apps", "main", "tests",
                                "fixtures", "tutorial.xls")
        self._publish_xls_form_to_project(xlsform_path=xls_path)

        xls_file_path = os.path.join(settings.PROJECT_ROOT, "apps", "logger",
                                     "fixtures",
                                     "external_choice_form_v1.xlsx")
        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        # Set require auth to true
        self.user.profile.require_auth = True
        self.user.profile.save()
        request = self.factory.get('/', {'formID': self.xform.id_string})
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)

        # Test for authenticated user but unrecognized formID
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/', {'formID': 'unrecognizedID'})
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # Test for authenticated user and valid formID
        request = self.factory.get('/', {'formID': self.xform.id_string})
        self.assertTrue(self.user.profile.require_auth)
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList2.xml')

        with open(path, encoding='utf-8') as f:
            form_list = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk,
                    'version': self.xform.version}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list % data)

        # Test for shared forms
        # Create user Alice
        alice_data = {
            'username': 'alice',
            'email': 'alice@localhost.com',
            'password1': 'alice',
            'password2': 'alice'
        }
        alice_profile = self._create_user_profile(alice_data)

        # check that she can authenticate successfully
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('alice', 'alice')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        # share Bob's project with Alice
        data = {
            'username': 'alice',
            'role': ReadOnlyRole.name
        }
        request = self.factory.post('/', data=data, **self.extra)
        share_view = ProjectViewSet.as_view({'post': 'share'})
        project_id = self.project.pk
        response = share_view(request, pk=project_id)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        request = self.factory.get('/', {'formID': self.xform.id_string})
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('alice', 'alice')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='alice')
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList2.xml')

        with open(path, encoding='utf-8') as f:
            form_list = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk,
                    "version": self.xform.version}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list % data)

        # Bob's profile
        bob_profile = self.user

        # Submit form as Alice
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, 'alice')

        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "good_eats_multilang", "good_eats_multilang.xls")
        self._publish_xls_form_to_project(xlsform_path=path)
        self.assertTrue(OwnerRole.user_has_role(alice_profile.user,
                                                self.xform))

        # Share Alice's form with Bob
        ReadOnlyRole.add(bob_profile, self.xform)
        self.assertTrue(ReadOnlyRole.user_has_role(bob_profile, self.xform))

        # Get unrecognized formID as bob
        request = self.factory.get('/', {'formID': 'unrecognizedID'})
        response = self.view(request, username=bob_profile.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=bob_profile.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # Get Alice's form as Bob
        request = self.factory.get('/', {'formID': 'good_eats_multilang'})
        response = self.view(request, username=bob_profile.username)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=bob_profile.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['formID'], 'good_eats_multilang')

    def test_get_xform_list_xform_pk_filter(self):
        """
        Test formList xform_pk filter for authenticated user.
        """
        self.user.profile.require_auth = True
        self.user.profile.save()
        request = self.factory.get('/')
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk + 10000)
        self.assertEqual(response.status_code, 404)

        request = self.factory.get('/')
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        # existing form is in result when xform_pk filter is in use.
        response = self.view(request, username=self.user.username,
                             xform_pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')

        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_get_xform_list_of_logged_in_user_with_username_param(self):
        # publish 2 forms as bob
        xls_path = os.path.join(settings.PROJECT_ROOT, "apps", "main", "tests",
                                "fixtures", "tutorial.xls")
        self._publish_xls_form_to_project(xlsform_path=xls_path)

        xls_file_path = os.path.join(settings.PROJECT_ROOT, "apps", "logger",
                                     "fixtures",
                                     "external_choice_form_v1.xlsx")
        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        # change one of bob's forms to public
        xform = self.user.xforms.first()
        xform.shared = True
        xform.save()
        xform_id_string = xform.id_string

        # check that bob still has 2 private forms
        self.assertEqual(self.user.xforms.filter(shared=False).count(), 2)

        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='bob')
        # check that bob's request is succesful and it returns both public and
        # private forms that belong to bob
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        alice_data = {
            'username': 'alice',
            'email': 'alice@localhost.com',
        }
        self._login_user_and_profile(extra_post_data=alice_data)
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('alice', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='bob')
        # check that alice's request is succesful and it returns public forms
        # owned by bob
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].get('formID'), xform_id_string)

    def test_get_xform_list_with_malformed_cookie(self):
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request.COOKIES['__enketo'] = 'hello'
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data.get('detail'),
            u'JWT DecodeError: Not enough segments')

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_read_only_users_get_non_empty_formlist_using_preview_formlist(
            self, mock_send_mail):
        alice_data = {
            'username': 'alice',
            'email': 'alice@localhost.com',
            'password1': 'alice',
            'password2': 'alice'
        }
        alice_profile = self._create_user_profile(alice_data)

        self.assertFalse(
            ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        # share bob's project with alice
        data = {
            'username': 'alice',
            'role': ReadOnlyRole.name,
            'email_msg': 'I have shared the project with you'
        }
        request = self.factory.post('/', data=data, **self.extra)
        share_view = ProjectViewSet.as_view({'post': 'share'})
        projectid = self.project.pk
        response = share_view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(
            ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        # check that she can authenticate successfully
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('alice', 'alice')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='bob')
        self.assertEqual(response.status_code, 200)
        # check that alice gets an empty response when requesting bob's
        # formlist
        self.assertEqual(response.data, [])

        # set endpoint to preview formList
        self.view = PreviewXFormListViewSet.as_view({"get": "list"})

        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(response.data, [])
        auth = DigestAuth('alice', 'alice')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='bob')
        self.assertEqual(response.status_code, 200)
        # check that alice does NOT get an empty response when requesting bob's
        # formlist when using the preview formlist endpoint
        self.assertNotEqual(response.data, [])

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_get_xform_list_with_shared_forms(self, mock_send_mail):
        # create user alice
        alice_data = {
            'username': 'alice',
            'email': 'alice@localhost.com',
            'password1': 'alice',
            'password2': 'alice'
        }
        alice_profile = self._create_user_profile(alice_data)

        # check that she can authenticate successfully
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('alice', 'alice')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            ReadOnlyRole.user_has_role(alice_profile.user, self.project))
        # share bob's project with her
        data = {
            'username': 'alice',
            'role': ReadOnlyRole.name,
            'email_msg': 'I have shared the project with you'
        }
        request = self.factory.post('/', data=data, **self.extra)
        share_view = ProjectViewSet.as_view({'post': 'share'})
        projectid = self.project.pk
        response = share_view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(
            ReadOnlyRole.user_has_role(alice_profile.user, self.project))

        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('alice', 'alice')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='alice')
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')

        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)
            download_url = ('<downloadUrl>http://testserver/%s/'
                            'forms/%s/form.xml</downloadUrl>') % (
                                self.user.username, self.xform.id)
            # check that bob's form exists in alice's formList
            self.assertTrue(download_url in content)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_get_xform_list_inactive_form(self):
        self.xform.downloadable = False
        self.xform.save()
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        xml = u'<?xml version="1.0" encoding="utf-8"?>\n<xforms '
        xml += u'xmlns="http://openrosa.org/xforms/xformsList"></xforms>'
        content = response.render().content.decode('utf-8')
        self.assertEqual(content, xml)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Content-Type'], 'text/xml; charset=utf-8')

    def test_get_xform_list_anonymous_user(self):
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')

        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_get_xform_list_anonymous_user_require_auth(self):
        self.user.profile.require_auth = True
        self.user.profile.save()
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        response = self.view(request, username=self.user.username)
        self.assertEqual(response.status_code, 401)

    def test_get_xform_list_other_user_with_no_role(self):
        request = self.factory.get('/')
        response = self.view(request)
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        self.assertFalse(
            ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

        auth = DigestAuth('alice', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        content = response.render().content.decode('utf-8')
        self.assertNotIn(self.xform.id_string, content)
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>\n<xforms ',
                      content)
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
            ReadOnlyRole.user_has_role(alice_profile.user, self.xform))

        auth = DigestAuth('alice', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        content = response.render().content.decode('utf-8')
        self.assertNotIn(self.xform.id_string, content)
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>\n<xforms ',
                      content)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Content-Type'], 'text/xml; charset=utf-8')

    def test_get_xform_list_other_user_with_dataentry_role(self):
        request = self.factory.get('/')
        response = self.view(request)
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        DataEntryRole.add(alice_profile.user, self.xform)

        self.assertTrue(
            DataEntryRole.user_has_role(alice_profile.user, self.xform))

        auth = DigestAuth('alice', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'formList.xml')

        with open(path, encoding='utf-8') as f:
            form_list_xml = f.read().strip()
            data = {"hash": self.xform.hash, "pk": self.xform.pk}
            content = response.render().content.decode('utf-8')
            self.assertEqual(content, form_list_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def test_retrieve_xform_xml(self):
        self.view = XFormListViewSet.as_view(
            {
                "get": "retrieve",
                "head": "retrieve"
            }
        )
        request = self.factory.head('/')
        response = self.view(request, pk=self.xform.pk)
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__), '..', 'fixtures',
            'Transportation Form.xml')

        with open(path, encoding='utf-8') as f:
            form_xml = f.read().strip()
            data = {"form_uuid": self.xform.uuid}
            content = response.render().content.decode('utf-8').strip()
            content = content.replace(self.xform.version, u"20141112071722")
            self.assertEqual(content, form_xml % data)
            self.assertTrue(response.has_header('X-OpenRosa-Version'))
            self.assertTrue(
                response.has_header('X-OpenRosa-Accept-Content-Length'))
            self.assertTrue(response.has_header('Date'))
            self.assertEqual(response['Content-Type'],
                             'text/xml; charset=utf-8')

    def _load_metadata(self, xform=None):
        data_value = "screenshot.png"
        data_type = 'media'
        fixture_dir = os.path.join(settings.PROJECT_ROOT, "apps", "main",
                                   "tests", "fixtures", "transportation")
        path = os.path.join(fixture_dir, data_value)
        xform = xform or self.xform

        self._add_form_metadata(xform, data_type, data_value, path)

    def test_retrieve_xform_manifest(self):
        self._load_metadata(self.xform)
        self.view = XFormListViewSet.as_view(
            {
                "get": "manifest",
                "head": "manifest"
            }
        )
        request = self.factory.head('/')

        response = self.view(request, pk=self.xform.pk)
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)

        manifest_xml = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://openrosa.org/xforms/xformsManifest"><mediaFile><filename>screenshot.png</filename><hash>%(hash)s</hash><downloadUrl>http://testserver/bob/xformsMedia/%(xform)s/%(pk)s.png</downloadUrl></mediaFile></manifest>"""  # noqa
        data = {
            "hash": self.metadata.hash,
            "pk": self.metadata.pk,
            "xform": self.xform.pk
        }
        content = response.render().content.decode('utf-8').strip()
        self.assertEqual(content, manifest_xml % data)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Content-Type'], 'text/xml; charset=utf-8')

    def test_retrieve_xform_manifest_anonymous_user(self):
        self._load_metadata(self.xform)
        self.view = XFormListViewSet.as_view({"get": "manifest"})
        request = self.factory.get('/')
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 401)
        response = self.view(
            request, pk=self.xform.pk, username=self.user.username)
        self.assertEqual(response.status_code, 200)

        manifest_xml = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://openrosa.org/xforms/xformsManifest"><mediaFile><filename>screenshot.png</filename><hash>%(hash)s</hash><downloadUrl>http://testserver/bob/xformsMedia/%(xform)s/%(pk)s.png</downloadUrl></mediaFile></manifest>"""  # noqa
        data = {
            "hash": self.metadata.hash,
            "pk": self.metadata.pk,
            "xform": self.xform.pk
        }
        content = response.render().content.decode('utf-8').strip()
        self.assertEqual(content, manifest_xml % data)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(
            response.has_header('X-OpenRosa-Accept-Content-Length'))
        self.assertTrue(response.has_header('Date'))
        self.assertEqual(response['Content-Type'], 'text/xml; charset=utf-8')

    def test_retrieve_xform_manifest_anonymous_user_require_auth(self):
        self.user.profile.require_auth = True
        self.user.profile.save()
        self._load_metadata(self.xform)
        self.view = XFormListViewSet.as_view({"get": "manifest"})
        request = self.factory.get('/')
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 401)
        response = self.view(
            request, pk=self.xform.pk, username=self.user.username)
        self.assertEqual(response.status_code, 401)

    def test_retrieve_xform_media(self):
        self._load_metadata(self.xform)
        self.view = XFormListViewSet.as_view(
            {
                "get": "media",
                "head": "media"
            }
        )
        request = self.factory.head('/')
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='png')
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='png')
        self.assertEqual(response.status_code, 200)

    def test_retrieve_xform_media_anonymous_user(self):
        self._load_metadata(self.xform)
        self.view = XFormListViewSet.as_view({"get": "media"})
        request = self.factory.get('/')
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='png')
        self.assertEqual(response.status_code, 401)

        response = self.view(
            request,
            pk=self.xform.pk,
            username=self.user.username,
            metadata=self.metadata.pk,
            format='png')
        self.assertEqual(response.status_code, 200)

    def test_retrieve_xform_media_anonymous_user_require_auth(self):
        self.user.profile.require_auth = True
        self.user.profile.save()
        self._load_metadata(self.xform)
        self.view = XFormListViewSet.as_view({"get": "media"})
        request = self.factory.get('/')
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='png')
        self.assertEqual(response.status_code, 401)

    def test_retrieve_xform_media_linked_xform(self):
        data_type = 'media'
        data_value = 'xform {} transportation'.format(self.xform.pk)
        self._add_form_metadata(self.xform, data_type, data_value)
        self._make_submissions()
        self.xform.refresh_from_db()

        self.view = XFormListViewSet.as_view(
            {
                "get": "manifest",
                "head": "manifest"
            }
        )
        request = self.factory.head('/')
        response = self.view(request, pk=self.xform.pk)
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['filename'], 'transportation.csv')
        self.assertEqual(
            response.data[0]['hash'], 'md5:%s' % md5(
                self.xform.last_submission_time.isoformat().encode(
                    'utf-8')).hexdigest())

        self.view = XFormListViewSet.as_view(
            {
                "get": "media",
                "head": "media"
            }
        )
        request = self.factory.get('/')
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='csv')
        self.assertEqual(response.status_code, 401)

        request = self.factory.head('/')
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='csv')
        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(
            request, pk=self.xform.pk, metadata=self.metadata.pk, format='csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'],
                         'attachment; filename=transportation.csv')

    def test_retrieve_xform_manifest_linked_form(self):
        # for linked forms check if manifest media download url for csv
        # has a group_delimiter param
        data_type = 'media'
        data_value = 'xform {} transportation'.format(self.xform.pk)
        media = self._add_form_metadata(self.xform, data_type, data_value)

        self.view = XFormListViewSet.as_view(
            {
                "get": "manifest",
                "head": "manifest"
            }
        )

        # sign in bob
        request = self.factory.head('/')
        auth_response = self.view(request, pk=self.xform.pk)
        auth = DigestAuth('bob', 'bobbob')

        # set up bob's request
        request = self.factory.get('/xformsManifest')
        request.META.update(auth(request.META, auth_response))

        # make request
        response = self.view(request, pk=self.xform.pk, format='csv')

        # test
        manifest_media_url = '{}{}'.format(
            media.data['media_url'],
            '?group_delimiter=.&repeat_index_tags=_,_')
        download_url = response.data[0]['downloadUrl']
        self.assertEqual(manifest_media_url, download_url)

        url = '/bob/xformsMedia/{}/{}.csv?group_delimiter=.'\
            .format(self.xform.pk, self.metadata.pk)
        username = 'bob'
        password = 'bob'

        client = DigestClient()
        client.set_authorization(username, password, 'Digest')

        req = client.get(url)
        self.assertEqual(req.status_code, 200)

        # enable meta perms
        data_value = "editor-minor|dataentry"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        req = client.get(url)
        self.assertEqual(req.status_code, 401)

    def test_xform_3gp_media_type(self):

        for fmt in ["png", "jpg", "mp3", "3gp", "wav"]:
            url = reverse(
                'xform-media',
                kwargs={
                    'username': 'bob',
                    'pk': 1,
                    'metadata': '1234',
                    'format': fmt
                })

            self.assertEqual(url, '/bob/xformsMedia/1/1234.{}'.format(fmt))

    def test_get_xform_anonymous_user_xform_require_auth(self):
        self.view = XFormListViewSet.as_view(
            {
                "get": "retrieve",
                "head": "retrieve"
            }
        )
        request = self.factory.head('/')
        response = self.view(request, username='bob', pk=self.xform.pk)
        # no authentication prompted
        self.assertEqual(response.status_code, 200)

        self.assertFalse(self.xform.require_auth)
        self.assertFalse(self.user.profile.require_auth)

        self.xform.require_auth = True
        self.xform.save()

        request = self.factory.head('/')
        response = self.view(request, username='bob', pk=self.xform.pk)
        # authentication prompted
        self.assertEqual(response.status_code, 401)

        auth = DigestAuth('bob', 'bobbob')
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        response = self.view(request, username='bob', pk=self.xform.pk)
        # success with authentication
        self.assertEqual(response.status_code, 200)

    def test_manifest_url_tag_is_not_present_when_no_media(self):
        """
        Test that content does not contain a manifest url
        only when the form has no media
        """
        request = self.factory.get('/')
        view = XFormListViewSet.as_view({"get": "list"})
        response = view(request, username='bob', pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        content = response.render().content.decode('utf-8')
        manifest_url = ('<manifestUrl></manifestUrl>')
        self.assertNotIn(manifest_url, content)

        # Add media and test that manifest url exists
        data_type = 'media'
        data_value = 'xform {} transportation'.format(self.xform.pk)
        self._add_form_metadata(self.xform, data_type, data_value)
        response = view(request, username='bob', pk=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        content = response.render().content.decode('utf-8')
        manifest_url = (
            '<manifestUrl>http://testserver/%s/xformsManifest'
            '/%s</manifestUrl>') % (self.user.username, self.xform.id)
        self.assertTrue(manifest_url in content)
