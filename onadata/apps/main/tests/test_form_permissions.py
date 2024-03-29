import os

from django.urls import reverse
from guardian.shortcuts import assign_perm, remove_perm

from onadata.apps.logger.models import XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import set_perm, show, edit, api, profile
from onadata.apps.viewer.views import map_view


class TestFormPermissions(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form()
        s = 'transport_2011-07-25_19-05-49'
        self._make_submission(os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'))
        self.submission = self.xform.instances.reverse()[0]
        self.url = reverse(map_view, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string})
        self.perm_url = reverse(set_perm, kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        self.edit_url = reverse(edit, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })
        self.show_url = reverse(show, kwargs={'uuid': self.xform.uuid})
        self.show_normal_url = reverse(show, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })
        self.api_url = reverse(api, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })

    def test_set_permissions_for_user(self):
        self._create_user_and_login('alice')
        self.assertEqual(self.user.has_perm('change_xform', self.xform), False)
        assign_perm('change_xform', self.user, self.xform)
        self.assertEqual(self.user.has_perm('change_xform', self.xform), True)
        xform = self.xform
        self._publish_transportation_form()
        self.assertNotEqual(xform, self.xform)
        self.assertEqual(self.user.has_perm('change_xform', self.xform), True)

    def test_allow_map(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_restrict_map_for_anon(self):
        response = self.anon.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_restrict_map_for_not_owner(self):
        self._create_user_and_login('alice')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_allow_map_if_shared(self):
        self.xform.shared_data = True
        self.xform.save()
        response = self.anon.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_allow_map_if_user_given_permission(self):
        self._create_user_and_login('alice')
        assign_perm('change_xform', self.user, self.xform)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_disallow_map_if_user_permission_revoked(self):
        self._create_user_and_login('alice')
        assign_perm('change_xform', self.user, self.xform)
        response = self.client.get(self.url)
        remove_perm('change_xform', self.user, self.xform)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_require_owner_to_add_perm(self):
        response = self.anon.post(self.perm_url)
        self.assertContains(response, 'Permission denied.', status_code=403)
        self._create_user_and_login('alice')
        response = self.client.post(self.perm_url)
        self.assertContains(response, 'Permission denied.', status_code=403)

    def test_add_view_to_user(self):
        user = self._create_user('alice', 'alice')
        response = self.client.post(self.perm_url, {
            'for_user': user.username, 'perm_type': 'view'})
        self.assertEqual(response.status_code, 302)
        alice = self._login('alice', 'alice')
        response = alice.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_add_view_permisions_to_user(self):
        user = self._create_user('alice', 'alice')
        response = self.client.post(self.perm_url, {
            'for_user': user.username, 'perm_type': 'view'})
        self.assertEqual(response.status_code, 302)
        alice = self._login('alice', 'alice')
        response = alice.get(self.show_url)
        self.assertEqual(response.status_code, 302)
        response = alice.get(self.show_normal_url)
        self.assertContains(response, 'Submissions:')

    def test_add_edit_to_user(self):
        user = self._create_user('alice', 'alice')
        response = self.client.post(self.perm_url, {
            'for_user': user.username, 'perm_type': 'edit'})
        self.assertEqual(response.status_code, 302)
        alice = self._login('alice', 'alice')
        response = alice.post(self.edit_url)
        self.assertEqual(response.status_code, 302)

    def test_public_with_link_to_share(self):
        response = self.client.post(self.perm_url, {
            'for_user': 'all', 'perm_type': 'link'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MetaData.public_link(self.xform), True)
        response = self.anon.get(self.show_url)
        self.assertRedirects(response, self.show_normal_url)

    def test_private_set_link_to_share_off(self):
        response = self.client.post(self.perm_url, {'for_user': 'all',
                                    'perm_type': 'link'})
        self.assertEqual(MetaData.public_link(self.xform), True)
        response = self.anon.get(self.show_url)
        self.assertRedirects(response, self.show_normal_url)
        response = self.client.post(self.perm_url, {'for_user': 'none',
                                    'perm_type': 'link'})
        self.assertEqual(MetaData.public_link(self.xform), False)
        response = self.anon.get(self.show_url)
        self.assertEqual(response.status_code, 302)
        # follow redirect
        response = self.anon.get(response['Location'])
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'],
                            '%s%s' % (self.base_url, self.show_normal_url))

    def test_only_access_shared_link_form(self):
        response = self.client.post(self.perm_url, {'for_user': 'all',
                                    'perm_type': 'link'})
        self.assertEqual(MetaData.public_link(self.xform), True)
        # publish a second form to make sure the user cant access other forms
        self._publish_xls_file(os.path.join(
            self.this_directory, "fixtures", "csv_export", "tutorial.xlsx"))
        xform_2 = XForm.objects.order_by('pk').reverse()[0]
        url_2 = reverse(show, kwargs={
            'username': self.user.username,
            'id_string': xform_2.id_string
        })
        response = self.anon.get(url_2)
        self.assertRedirects(response, "/")

    def test_public_with_link_to_share_toggle_on(self):
        response = self.client.post(self.perm_url, {'for_user': 'toggle',
                                    'perm_type': 'link'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MetaData.public_link(self.xform), True)
        response = self.anon.get(self.show_url)
        self.assertRedirects(response,  self.show_normal_url)
        response = self.anon.get(self.show_normal_url)
        self.assertEqual(response.status_code, 200)

    def test_private_set_link_to_share_toggle_off(self):
        response = self.client.post(self.perm_url, {'for_user': 'toggle',
                                    'perm_type': 'link'})
        self.assertEqual(MetaData.public_link(self.xform), True)
        response = self.anon.get(self.show_url)
        self.assertRedirects(response,  self.show_normal_url)
        response = self.client.post(self.perm_url, {'for_user': 'none',
                                    'perm_type': 'link'})
        self.assertEqual(MetaData.public_link(self.xform), False)
        response = self.anon.get(self.show_url)
        # follow redirect
        response = self.anon.get(response['Location'])
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'],
                            '%s%s' % (self.base_url, self.show_normal_url))

    def test_show_list_of_users_shared_with(self):
        new_username = 'alice'
        user = self._create_user(new_username, 'alice')
        response = self.client.post(self.perm_url, {'for_user': user.username,
                                    'perm_type': 'view'})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(self.show_normal_url)
        self.assertContains(response, new_username)

    def test_anon_reject_api(self):
        response = self.anon.get(self.api_url)
        self.assertEqual(response.status_code, 403)

    def test_client_allow_api(self):
        response = self.client.get(self.api_url, {'query': '{}'})
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, 200)

    def test_view_shared_form(self):
        user = self._create_user('alice', 'alice')
        response = self.client.post(self.perm_url, {'for_user': user.username,
                                                    'perm_type': 'view'})
        self.assertEqual(response.status_code, 302)
        alice = self._login('alice', 'alice')
        response = alice.get(self.show_url)
        self.assertEqual(response.status_code, 302)
        response = alice.get(self.show_normal_url)
        self.assertContains(response, 'Submissions:')
        dashboard_url = reverse(profile, kwargs={
            'username': 'alice'
        })
        response = alice.get(dashboard_url)
        self.assertContains(
            response, "%s</a> <span class=\"label label-shared"
            "\">Shared by %s</span>" % (
                self.xform.title, self.xform.user.username)
        )

    def test_remove_permissions_from_user(self):
        user = self._create_user('alice', 'alice')
        # Grant all permissions
        for perm_type in ('view', 'edit', 'report'):
            response = self.client.post(self.perm_url, {
                'for_user': user.username, 'perm_type': perm_type})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(user.has_perm('view_xform', self.xform), True)
        self.assertEqual(user.has_perm('change_xform', self.xform), True)
        self.assertEqual(user.has_perm('report_xform', self.xform), True)
        # Revoke all permissions
        response = self.client.post(self.perm_url, {
            'for_user': user.username, 'perm_type': 'remove'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(user.has_perm('view_xform', self.xform), False)
        self.assertEqual(user.has_perm('change_xform', self.xform), False)
        self.assertEqual(user.has_perm('report_xform', self.xform), False)
