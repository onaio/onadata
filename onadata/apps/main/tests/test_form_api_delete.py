from datetime import datetime

from django.urls import reverse

from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import delete_data
from onadata.apps.viewer.models.parsed_instance import query_data, query_fields_data
from onadata.libs.permissions import EditorRole, ReadOnlyRole


class TestFormAPIDelete(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()
        self.delete_url = reverse(
            delete_data,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        self.data_args = {
            "xform": self.xform,
            "query": "{}",
            "limit": 1,
            "sort": "-pk",
            "fields": '["_id","_uuid"]',
        }

    def _get_data(self):
        cursor = query_data(**self.data_args)
        records = list(record for record in cursor)
        return records

    def test_get_request_does_not_delete(self):
        # not allowed 405
        count = Instance.objects.filter(deleted_at=None).count()
        response = self.anon.get(self.delete_url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Instance.objects.filter(deleted_at=None).count(), count)

    def test_anon_user_cant_delete(self):
        # Only authenticated user are allowed to access the url
        count = Instance.objects.filter(deleted_at=None).count()
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        # delete
        params = {"id": instance.id}
        response = self.anon.post(self.delete_url, params)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('two_factor:login')}?next=", response["Location"])
        self.assertEqual(Instance.objects.filter(deleted_at=None).count(), count)

    def test_delete_shared(self):
        # Test if someone can delete data from a shared form
        self.xform.shared = True
        self.xform.save()
        self._create_user_and_login("jo")
        count = Instance.objects.filter(deleted_at=None).count()
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        # delete
        params = {"id": instance.id}
        response = self.client.post(self.delete_url, params)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Instance.objects.filter(deleted_at=None).count(), count)

    def test_owner_can_delete(self):
        # Test if Form owner can delete
        # check record exist before delete and after delete
        count = Instance.objects.filter(deleted_at=None).count()
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        self.assertEqual(instance.deleted_at, None)
        # delete
        params = {"id": instance.id}
        response = self.client.post(self.delete_url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Instance.objects.filter(deleted_at=None).count(), count - 1)
        instance = Instance.objects.get(id=instance.id)
        self.assertTrue(isinstance(instance.deleted_at, datetime))
        self.assertNotEqual(instance.deleted_at, None)
        query = '{"_id": %s}' % instance.id
        self.data_args.update({"query": query})
        after = list(query_fields_data(**self.data_args))
        self.assertEqual(len(after), count - 1)

    def test_cannot_delete_submission_of_another_form(self):
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        self._create_user_and_login("alice")
        self._publish_transportation_form()
        delete_url = reverse(
            delete_data,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )
        response = self.client.post(delete_url, {"id": instance.id})
        self.assertEqual(response.status_code, 404)
        instance.refresh_from_db()
        self.assertIsNone(instance.deleted_at)

    def test_read_only_collaborator_cannot_delete_submission(self):
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        self._create_user_and_login("alice")
        ReadOnlyRole.add(self.user, self.xform)
        response = self.client.post(self.delete_url, {"id": instance.id})
        self.assertEqual(response.status_code, 403)
        instance.refresh_from_db()
        self.assertIsNone(instance.deleted_at)

    def test_editor_can_delete_submission(self):
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        self._create_user_and_login("alice")
        EditorRole.add(self.user, self.xform)
        response = self.client.post(self.delete_url, {"id": instance.id})
        self.assertEqual(response.status_code, 200)
        instance.refresh_from_db()
        self.assertIsNotNone(instance.deleted_at)

    def test_cannot_delete_submission_of_form_with_shared_data(self):
        self.xform.shared_data = True
        self.xform.save()
        instance = Instance.objects.filter(xform=self.xform).latest("date_created")
        self._create_user_and_login("alice")
        response = self.client.post(self.delete_url, {"id": instance.id})
        self.assertEqual(response.status_code, 403)
        instance.refresh_from_db()
        self.assertIsNone(instance.deleted_at)
