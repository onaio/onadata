from onadata.apps.main.tests.test_base import TestBase as CommonTestBase

from rest_framework.test import APIClient

from onadata.apps.logger.models import Entity, EntityList


class TestBase(CommonTestBase):
    """Base class for test cases"""

    def setUp(self):
        super().setUp()

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user.auth_token}")


class EntityTestBase(TestBase):
    """Base class for Entity test cases"""

    def setUp(self):
        super().setUp()

        self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.get(name="trees")
        self.entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
        self.data = {"data": {"species": "mora"}}


class EntityListTestCase(EntityTestBase):
    """Entity list, create tests"""

    def setUp(self):
        super().setUp()

        self.url = f"/api/v2/entity-lists/{self.entity_list.pk}/entities"

    def test_get(self):
        """GET list of Entities"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_create(self):
        """POST Entity"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


class EntityDetailTestCase(EntityTestBase):
    """Entity retrieve, update, partial_update, destroy tests"""

    def setUp(self):
        super().setUp()

        self.data = {"data": {"species": "mora"}}
        self.url = (
            f"/api/v2/entity-lists/{self.entity_list.pk}/entities/{self.entity.pk}"
        )

    def test_get(self):
        """GET Entity"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_patch(self):
        """PATCH Entity"""
        response = self.client.patch(self.url, data=self.data, format="json")
        self.assertEqual(response.status_code, 200)

    def test_put(self):
        """PUT Entity"""
        response = self.client.put(self.url, data=self.data, format="json")
        self.assertEqual(response.status_code, 200)

    def test_delete(self):
        """DELETE Entity"""
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 204)
