from datetime import datetime

from django.core.urlresolvers import reverse

from onadata.apps.main.views import delete_data
from onadata.apps.viewer.models.parsed_instance import query_data
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.tests.test_base import TestBase


class TestFormAPIDelete(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()
        self.delete_url = reverse(delete_data, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })
        self.data_args = {
            'xform': self.xform,
            'query': "{}", 'limit': 1,
            'sort': '-pk', 'fields': '["_id","_uuid"]'}

    def _get_data(self):
        cursor = query_data(**self.data_args)
        records = list(record for record in cursor)
        return records

    def test_get_request_does_not_delete(self):
        # not allowed 405
        count = Instance.objects.filter(deleted_at=None).count()
        response = self.anon.get(self.delete_url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            Instance.objects.filter(deleted_at=None).count(), count)

    def test_anon_user_cant_delete(self):
        # Only authenticated user are allowed to access the url
        count = Instance.objects.filter(deleted_at=None).count()
        instance = Instance.objects.filter(
            xform=self.xform).latest('date_created')
        # delete
        params = {'id': instance.id}
        response = self.anon.post(self.delete_url, params)
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts/login/?next=", response["Location"])
        self.assertEqual(
            Instance.objects.filter(deleted_at=None).count(), count)

    def test_delete_shared(self):
        # Test if someone can delete data from a shared form
        self.xform.shared = True
        self.xform.save()
        self._create_user_and_login("jo")
        count = Instance.objects.filter(deleted_at=None).count()
        instance = Instance.objects.filter(
            xform=self.xform).latest('date_created')
        # delete
        params = {'id': instance.id}
        response = self.client.post(self.delete_url, params)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            Instance.objects.filter(deleted_at=None).count(), count)

    def test_owner_can_delete(self):
        # Test if Form owner can delete
        # check record exist before delete and after delete
        count = Instance.objects.filter(deleted_at=None).count()
        instance = Instance.objects.filter(
            xform=self.xform).latest('date_created')
        self.assertEqual(instance.deleted_at, None)
        # delete
        params = {'id': instance.id}
        response = self.client.post(self.delete_url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Instance.objects.filter(deleted_at=None).count(), count - 1)
        instance = Instance.objects.get(id=instance.id)
        self.assertTrue(isinstance(instance.deleted_at, datetime))
        self.assertNotEqual(instance.deleted_at, None)
        query = '{"_id": %s}' % instance.id
        self.data_args.update({"query": query})
        after = [r for r in query_data(**self.data_args)]
        self.assertEqual(len(after), count - 1)
