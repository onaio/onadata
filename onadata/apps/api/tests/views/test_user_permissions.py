import json
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django_digest.test import Client as DigestClient
from rest_framework.renderers import JSONRenderer

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.libs import permissions as role
from onadata.libs.serializers.xform_serializer import XFormSerializer


class TestUserPermissions(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()

    def test_can_add_xform_to_other_account(self):
        view = XFormViewSet.as_view({
            'post': 'create'
        })
        data = {
            'owner': 'http://testserver/api/v1/users/bob',
            'public': False,
            'public_data': False,
            'description': u'transportation_2011_07_25',
            'downloadable': True,
            'allows_sms': False,
            'encrypted': False,
            'sms_id_string': u'transportation_2011_07_25',
            'id_string': u'transportation_2011_07_25',
            'title': u'transportation_2011_07_25',
            'bamboo_dataset': u''
        }
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")

        bob = self.user
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)

        with open(path) as xls_file:
            post_data = {'xls_file': xls_file, 'owner': 'bob'}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 403)

            role.ManagerRole.add(self.user, bob.profile)
            response = view(request)
            self.assertEqual(response.status_code, 201)

            xform = bob.xforms.all()[0]
            data.update({
                'url':
                'http://testserver/api/v1/forms/%s' % xform.pk
            })
            self.assertDictContainsSubset(data, response.data)

    def test_manager_can_update_xform(self):
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        view = XFormViewSet.as_view({
            'put': 'update'
        })
        description = 'DESCRIPTION'
        request = self.factory.get('/', **self.extra)
        xfs = XFormSerializer(instance=self.xform,
                              context={'request': request})
        data = json.loads(JSONRenderer().render(xfs.data))
        data.update({'public': True, 'description': description})

        self.assertFalse(self.xform.shared)

        request = self.factory.put('/', data=data, **self.extra)
        with self.assertRaises(ValidationError):
            response = view(request, pk=self.xform.id)
        self.assertFalse(self.xform.shared)

        role.ManagerRole.add(self.user, self.xform)
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=self.xform.id)

        self.xform.reload()
        self.assertTrue(self.xform.shared)
        self.assertEqual(self.xform.description, description)
        self.assertEqual(response.data['public'], True)
        self.assertEqual(response.data['description'], description)

    def test_manager_can_update_xform_tags(self):
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        view = XFormViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })
        formid = self.xform.pk

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        role.ManagerRole.add(self.user, self.xform)
        response = view(request, pk=formid)
        self.assertEqual(response.data, [])

        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])

        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, pk=formid, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_readonly_role(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        view = XFormViewSet.as_view({
            'get': 'retrieve',
            'put': 'update'
        })
        data_view = DataViewSet.as_view({'get': 'list'})
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        formid = self.xform.pk

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 403)

        role.ReadOnlyRole.add(self.user, self.xform)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 200)

        data = {'public': True, 'description': "Some description"}
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 403)

    def test_readonly_role_submission_when_requires_auth(self):
        self._publish_xls_form_to_project()
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com',
                      'password1': 'alice', 'password2': 'alice'}
        self._login_user_and_profile(extra_post_data=alice_data)
        role.ReadOnlyRole.add(self.user, self.xform)

        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances', s, s + '.xml') for s in self.surveys]
        client = DigestClient()
        client.set_authorization('alice', 'alice', 'Digest')
        self._make_submission(paths[0], username='bob', client=client)
        self.assertEqual(self.response.status_code, 403)

    def test_data_entry_role(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        view = XFormViewSet.as_view({
            'get': 'retrieve',
            'put': 'update'
        })
        data_view = DataViewSet.as_view({'get': 'list'})
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        formid = self.xform.pk

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 403)

        role.DataEntryRole.add(self.user, self.xform)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 200)

        data = {'public': True, 'description': "Some description"}
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 403)

    def test_data_entry_role_submission_when_requires_auth(self):
        self._publish_xls_form_to_project()
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com',
                      'password1': 'alice', 'password2': 'alice'}
        self._login_user_and_profile(extra_post_data=alice_data)
        role.DataEntryRole.add(self.user, self.xform)

        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances', s, s + '.xml') for s in self.surveys]
        client = DigestClient()
        client.set_authorization('alice', 'alice', 'Digest')
        self._make_submission(paths[0], username='bob', client=client)
        self.assertEqual(self.response.status_code, 201)

    def test_editor_role(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        view = XFormViewSet.as_view({
            'get': 'retrieve',
            'patch': 'update'
        })
        data_view = DataViewSet.as_view({'get': 'list'})
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        formid = self.xform.pk

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 403)

        role.EditorRole.add(self.user, self.xform)

        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 200)

    def test_editor_role_submission_when_requires_auth(self):
        self._publish_xls_form_to_project()
        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances_w_uuid', s, s + '.xml') for s in [
                'transport_2011-07-25_19-05-36',
                'transport_2011-07-25_19-05-36-edited']]
        self._make_submission(paths[0])
        self.user.profile.require_auth = True
        self.user.profile.save()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com',
                      'password1': 'alice', 'password2': 'alice'}
        self._login_user_and_profile(extra_post_data=alice_data)

        client = DigestClient()
        client.set_authorization('alice', 'alice', 'Digest')
        self._make_submission(paths[1], username='bob', client=client)
        self.assertEqual(self.response.status_code, 403)

        role.EditorRole.add(self.user, self.xform)
        self._make_submission(paths[1], username='bob', client=client)
        self.assertEqual(self.response.status_code, 201)

    def test_owner_role(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        view = XFormViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'delete': 'destroy'
        })
        data_view = DataViewSet.as_view({'get': 'list'})
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        formid = self.xform.pk

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 403)

        role.OwnerRole.add(self.user, self.xform)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        response = data_view(request, formid=formid)
        self.assertEqual(response.status_code, 200)

        xfs = XFormSerializer(instance=self.xform,
                              context={'request': request})
        data = json.loads(JSONRenderer().render(xfs.data))
        data.update({'public': True, 'description': "Some description"})
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 204)

    def test_org_creator_permissions(self):
        self._org_create()
        self.assertTrue(role.OwnerRole.has_role(self.user, self.organization))
