from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet as TestBase,
)
from onadata.libs.permissions import OwnerRole

from rest_framework.test import APIClient


class TestAbstractViewSet(TestBase):
    """Base class for test cases"""

    def setUp(self):
        super().setUp()

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user.auth_token}")


class EntityListTestCase(TestAbstractViewSet):
    """Entity list, create tests"""

    def setUp(self):
        super().setUp()

        self._create_entity()
        self.url = f"/api/v2/entity-lists/{self.entity_list.pk}/entities"
        OwnerRole.add(self.user, self.entity_list)

    def test_get(self):
        """GET list of Entities"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_create(self):
        """POST Entity"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)


class EntityDetailTestCase(TestAbstractViewSet):
    """Entity retrieve, update, partial_update, destroy tests"""

    def setUp(self):
        super().setUp()

        self._create_entity()
        self.data = {"data": {"species": "mora"}}
        self.url = (
            f"/api/v2/entity-lists/{self.entity_list.pk}/entities/{self.entity.pk}"
        )
        OwnerRole.add(self.user, self.entity_list)

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
        url = f"/api/v2/entity-lists/{self.entity_list.pk}/entities"
        response = self.client.delete(url, data={"entity_ids": [self.entity.pk]})
        self.assertEqual(response.status_code, 204)
