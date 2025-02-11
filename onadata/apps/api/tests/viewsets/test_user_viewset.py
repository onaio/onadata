# -*- coding: utf-8 -*-
"""
Test UserViewSet module.
"""

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.user_viewset import UserViewSet


class TestUserViewSet(TestAbstractViewSet):
    def setUp(self):
        super().setUp()
        self.data = {
            "id": self.user.pk,
            "username": "bob",
            "first_name": "Bob",
            "last_name": "erama",
        }

    def test_user_get(self):
        """Test authenticated user can access user info"""
        request = self.factory.get("/", **self.extra)

        # users list
        view = UserViewSet.as_view({"get": "list"})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.data])

        # user with username bob
        view = UserViewSet.as_view({"get": "retrieve"})
        response = view(request, username="bob")
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

        # user with username BoB, mixed case
        view = UserViewSet.as_view({"get": "retrieve"})
        response = view(request, username="BoB")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data, self.data)

        # Test can retrieve profile for usernames with _ . @ symbols
        alice_data = {
            "username": "alice.test@gmail.com",
            "email": "alice@localhost.com",
        }
        alice_profile = self._create_user_profile(alice_data)
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = view(request, username="alice.test@gmail.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], alice_data["username"])

        # user bob is_active = False
        self.user.is_active = False
        self.user.save()

        view = UserViewSet.as_view({"get": "retrieve"})
        response = view(request, username="BoB")
        self.assertEqual(response.status_code, 404)

    def test_user_anon(self):
        """Test anonymous user can access user info(except for list endpoint)"""
        request = self.factory.get("/")

        # users list endpoint returns 401 for anonymous users
        view = UserViewSet.as_view({"get": "list"})
        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data, {"detail": "Authentication credentials were not provided."}
        )

        # user with username bob
        view = UserViewSet.as_view({"get": "retrieve"})
        response = view(request, username="bob")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

        # Test with primary key
        response = view(request, username=self.user.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_get_user_using_email(self):
        alice_data = {
            "username": "alice",
            "email": "alice@localhost.com",
            "first_name": "Alice",
            "last_name": "Kamande",
        }
        alice_profile = self._create_user_profile(alice_data)
        data = [
            {
                "id": alice_profile.user.pk,
                "username": "alice",
                "first_name": "Alice",
                "last_name": "Kamande",
            }
        ]
        get_params = {
            "search": alice_profile.user.email,
        }
        view = UserViewSet.as_view({"get": "list"})
        request = self.factory.get("/", data=get_params)

        response = view(request)
        self.assertEqual(response.status_code, 401)
        error = {"detail": "Authentication credentials were not provided."}
        self.assertEqual(response.data, error)

        # authenticated
        request = self.factory.get("/", data=get_params, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

        get_params = {
            "search": "doesnotexist@email.com",
        }

        request = self.factory.get("/", data=get_params, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        # empty results
        self.assertEqual(response.data, [])

        get_params = {
            "search": "invalid@email.com",
        }

        request = self.factory.get("/", data=get_params, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        # empty results
        self.assertEqual(response.data, [])

    def test_get_non_org_users(self):
        self._org_create()

        view = UserViewSet.as_view({"get": "list"})

        all_users_request = self.factory.get("/", **self.extra)
        all_users_response = view(all_users_request)

        self.assertEqual(all_users_response.status_code, 200)
        self.assertEqual(
            len([u for u in all_users_response.data if u["username"] == "denoinc"]), 1
        )

        no_orgs_request = self.factory.get("/", data={"orgs": "false"}, **self.extra)
        no_orgs_response = view(no_orgs_request)

        self.assertEqual(no_orgs_response.status_code, 200)
        self.assertEqual(
            len([u for u in no_orgs_response.data if u["username"] == "denoinc"]), 0
        )
