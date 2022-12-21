# -*- coding: utf-8 -*-
"""
Tests the UserProfileViewSet.
"""
# pylint: disable=too-many-lines
import datetime
import json
import os
from six.moves.urllib.parse import urlparse, parse_qs

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import signals
from django.test.utils import override_settings
from django.utils.dateparse import parse_datetime
from django.utils import timezone

import requests
from django_digest.test import DigestAuth
from httmock import HTTMock, all_requests
from mock import patch, call
from registration.models import RegistrationProfile
from rest_framework.authtoken.models import Token

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.models import UserProfile
from onadata.apps.main.models.user_profile import set_kpi_formbuilder_permissions
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.serializers.user_profile_serializer import _get_first_last_names


User = get_user_model()


def _profile_data():
    return {
        "username": "deno",
        "first_name": "Dennis",
        "last_name": "erama",
        "email": "deno@columbia.edu",
        "city": "Denoville",
        "country": "US",
        "organization": "Dono Inc.",
        "website": "deno.com",
        "twitter": "denoerama",
        "require_auth": False,
        "password": "denodeno",
        "is_org": False,
        "name": "Dennis erama",
    }


# pylint: disable=attribute-defined-outside-init,too-many-public-methods
# pylint: disable=invalid-name,missing-class-docstring,missing-function-docstring,
# pylint: disable=consider-using-f-string
class TestUserProfileViewSet(TestAbstractViewSet):
    def setUp(self):
        super().setUp()
        self.view = UserProfileViewSet.as_view(
            {
                "get": "list",
                "post": "create",
                "patch": "partial_update",
                "put": "update",
            }
        )

    def tearDown(self):
        """
        Specific to clear cache between tests
        """
        super().tearDown()
        cache.clear()

    def test_profiles_list(self):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        data = self.user_profile_data()
        del data["metadata"]

        self.assertEqual(response.data, [data])

    def test_user_profile_list(self):
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(_profile_data()),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        data = {"users": "bob,deno"}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request)

        deno_profile_data = _profile_data()
        deno_profile_data.pop("password", None)
        user_deno = User.objects.get(username="deno")
        deno_profile_data.update(
            {
                "id": user_deno.pk,
                "url": "http://testserver/api/v1/profiles/%s" % user_deno.username,
                "user": "http://testserver/api/v1/users/%s" % user_deno.username,
                "gravatar": user_deno.profile.gravatar,
                "joined_on": user_deno.date_joined,
            }
        )

        self.assertEqual(response.status_code, 200)

        user_profile_data = self.user_profile_data()
        del user_profile_data["metadata"]

        self.assertEqual(
            sorted([dict(d) for d in response.data], key=lambda x: x["id"]),
            sorted([user_profile_data, deno_profile_data], key=lambda x: x["id"]),
        )
        self.assertEqual(len(response.data), 2)

        # Inactive user not in list
        user_deno.is_active = False
        user_deno.save()
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertNotIn(user_deno.pk, [user["id"] for user in response.data])

    def test_user_profile_list_with_and_without_users_param(self):
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(_profile_data()),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # anonymous user gets empty response
        request = self.factory.get("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # authenicated user without users query param only gets his/her profile
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        user_profile_data = self.user_profile_data()
        del user_profile_data["metadata"]

        self.assertDictEqual(user_profile_data, response.data[0])

        # authenicated user with blank users query param only gets his/her
        # profile
        data = {"users": ""}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertDictEqual(user_profile_data, response.data[0])

        # authenicated user with comma separated usernames as users query param
        # value gets profiles of the usernames provided
        data = {"users": "bob,deno"}
        request = self.factory.get("/", data=data, **self.extra)
        response = self.view(request)
        deno_profile_data = _profile_data()
        deno_profile_data.pop("password", None)
        user_deno = User.objects.get(username="deno")
        deno_profile_data.update(
            {
                "id": user_deno.pk,
                "url": "http://testserver/api/v1/profiles/%s" % user_deno.username,
                "user": "http://testserver/api/v1/users/%s" % user_deno.username,
                "gravatar": user_deno.profile.gravatar,
                "joined_on": user_deno.date_joined,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            [dict(i) for i in response.data], [user_profile_data, deno_profile_data]
        )

    def test_profiles_get(self):
        """Test get user profile"""
        view = UserProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Expected URL keyword argument `user`."}
        )

        # by username
        response = view(request, user="bob")
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.user_profile_data())

        # by username mixed case
        response = view(request, user="BoB")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data, self.user_profile_data())

        # by pk
        response = view(request, user=self.user.pk)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.user_profile_data())

    def test_profiles_get_anon(self):
        view = UserProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/")
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Expected URL keyword argument `user`."}
        )
        request = self.factory.get("/")
        response = view(request, user="bob")
        data = self.user_profile_data()
        del data["email"]
        del data["metadata"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)
        self.assertNotIn("email", response.data)

    def test_profiles_get_org_anon(self):
        self._org_create()
        self.client.logout()
        view = UserProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/")
        response = view(request, user=self.company_data["org"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], self.company_data["name"])
        self.assertIn("is_org", response.data)
        self.assertEqual(response.data["is_org"], True)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    @patch(
        (
            "onadata.libs.serializers.user_profile_serializer."
            "send_verification_email.delay"
        )
    )
    def test_profile_create(self, mock_send_verification_email):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data["name"]
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        password = data["password"]
        del data["password"]
        profile = UserProfile.objects.get(user__username=data["username"])
        data["id"] = profile.user.pk
        data["gravatar"] = profile.gravatar
        data["url"] = "http://testserver/api/v1/profiles/deno"
        data["user"] = "http://testserver/api/v1/users/deno"
        data["metadata"] = {}
        data["metadata"]["last_password_edit"] = profile.metadata["last_password_edit"]
        data["joined_on"] = profile.user.date_joined
        data["name"] = "%s %s" % ("Dennis", "erama")
        self.assertEqual(response.data, data)

        self.assertTrue(mock_send_verification_email.called)
        user = User.objects.get(username="deno")
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(password), password)

    def _create_user_using_profiles_endpoint(self, data):
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    @override_settings(VERIFIED_KEY_TEXT=None)
    def test_return_204_if_email_verification_variables_are_not_set(self):
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        view = UserProfileViewSet.as_view(
            {"get": "verify_email", "post": "send_verification_email"}
        )
        rp = RegistrationProfile.objects.get(user__username=data.get("username"))
        _data = {"verification_key": rp.activation_key}
        request = self.factory.get("/", data=_data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 204)

        data = {"username": data.get("username")}
        user = User.objects.get(username=data.get("username"))
        extra = {"HTTP_AUTHORIZATION": "Token %s" % user.auth_token}
        request = self.factory.post("/", data=data, **extra)
        response = view(request)
        self.assertEqual(response.status_code, 204)

    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    def test_verification_key_is_valid(self):
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        view = UserProfileViewSet.as_view({"get": "verify_email"})
        rp = RegistrationProfile.objects.get(user__username=data.get("username"))
        _data = {"verification_key": rp.activation_key}
        request = self.factory.get("/", data=_data)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_email_verified", response.data)
        self.assertIn("username", response.data)
        self.assertTrue(response.data.get("is_email_verified"))
        self.assertEqual(response.data.get("username"), data.get("username"))

        up = UserProfile.objects.get(user__username=data.get("username"))
        self.assertIn("is_email_verified", up.metadata)
        self.assertTrue(up.metadata.get("is_email_verified"))

    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    def test_verification_key_is_valid_with_redirect_url_set(self):
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        view = UserProfileViewSet.as_view({"get": "verify_email"})
        rp = RegistrationProfile.objects.get(user__username=data.get("username"))
        _data = {
            "verification_key": rp.activation_key,
            "redirect_url": "http://red.ir.ect",
        }
        request = self.factory.get("/", data=_data)
        response = view(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("is_email_verified", response.url)
        self.assertIn("username", response.url)

        string_query_params = urlparse(response.url).query
        dict_query_params = parse_qs(string_query_params)
        self.assertEqual(dict_query_params.get("is_email_verified"), ["True"])
        self.assertEqual(dict_query_params.get("username"), [data.get("username")])

        up = UserProfile.objects.get(user__username=data.get("username"))
        self.assertIn("is_email_verified", up.metadata)
        self.assertTrue(up.metadata.get("is_email_verified"))

    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    @patch(
        (
            "onadata.apps.api.viewsets.user_profile_viewset."
            "send_verification_email.delay"
        )
    )
    def test_sending_verification_email_succeeds(self, mock_send_verification_email):
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        data = {"username": data.get("username")}
        view = UserProfileViewSet.as_view({"post": "send_verification_email"})

        user = User.objects.get(username=data.get("username"))
        extra = {"HTTP_AUTHORIZATION": "Token %s" % user.auth_token}
        request = self.factory.post("/", data=data, **extra)
        response = view(request)
        self.assertTrue(mock_send_verification_email.called)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, "Verification email has been sent")

        user = User.objects.get(username=data.get("username"))
        self.assertFalse(user.profile.metadata.get("is_email_verified"))

    @override_settings(VERIFIED_KEY_TEXT=None)
    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    def test_sending_verification_email_fails(self):
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        view = UserProfileViewSet.as_view({"post": "send_verification_email"})

        # trigger permission error when username of requesting user is
        # different from username in post details
        request = self.factory.post("/", data={"username": "None"}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(REQUIRE_ODK_AUTHENTICATION=True)
    def test_profile_require_auth(self):
        """
        Test profile require_auth is True when REQUIRE_ODK_AUTHENTICATION is
        set to True.
        """
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data["name"]
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data.get("require_auth"))

    def test_profile_create_without_last_name(self):
        data = {
            "username": "deno",
            "first_name": "Dennis",
            "email": "deno@columbia.edu",
        }

        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

    def test_disallow_profile_create_w_same_username(self):
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertTrue("deno already exists" in response.data["username"][0])

    def test_profile_create_with_malfunctioned_email(self):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = {
            "username": "nguyenquynh",
            "first_name": "Nguy\u1ec5n Th\u1ecb",
            "last_name": "Di\u1ec5m Qu\u1ef3nh",
            "email": "onademo0+nguyenquynh@gmail.com\ufeff",
            "city": "Denoville",
            "country": "US",
            "organization": "Dono Inc.",
            "website": "nguyenquynh.com",
            "twitter": "nguyenquynh",
            "require_auth": False,
            "password": "onademo",
            "is_org": False,
        }

        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        password = data["password"]
        del data["password"]

        profile = UserProfile.objects.get(user__username=data["username"])
        data["id"] = profile.user.pk
        data["gravatar"] = profile.gravatar
        data["url"] = "http://testserver/api/v1/profiles/nguyenquynh"
        data["user"] = "http://testserver/api/v1/users/nguyenquynh"
        data["metadata"] = {}
        data["metadata"]["last_password_edit"] = profile.metadata["last_password_edit"]
        data["joined_on"] = profile.user.date_joined
        data["name"] = "%s %s" % ("Nguy\u1ec5n Th\u1ecb", "Di\u1ec5m Qu\u1ef3nh")
        self.assertEqual(response.data, data)

        user = User.objects.get(username="nguyenquynh")
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(password), password)

    def test_profile_create_with_invalid_username(self):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        data["username"] = "de"
        del data["name"]
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("username"),
            ["Ensure this field has at least 3 characters."],
        )

    def test_profile_create_anon(self):
        data = _profile_data()
        request = self.factory.post(
            "/api/v1/profiles", data=json.dumps(data), content_type="application/json"
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        del data["password"]
        del data["email"]
        profile = UserProfile.objects.get(user__username=data["username"])
        data["id"] = profile.user.pk
        data["gravatar"] = profile.gravatar
        data["url"] = "http://testserver/api/v1/profiles/deno"
        data["user"] = "http://testserver/api/v1/users/deno"
        data["metadata"] = {}
        data["metadata"]["last_password_edit"] = profile.metadata["last_password_edit"]
        data["joined_on"] = profile.user.date_joined
        self.assertEqual(response.data, data)
        self.assertNotIn("email", response.data)

    def test_profile_create_missing_name_field(self):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data["first_name"]
        del data["name"]
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        response.render()
        self.assertContains(
            response, "Either name or first_name should be provided", status_code=400
        )

    def test_split_long_name_to_first_name_and_last_name(self):
        name = (
            "(CPLTGL) Centre Pour la Promotion de la Liberte D'Expression "
            "et de la Tolerance Dans La Region de"
        )
        first_name, last_name = _get_first_last_names(name)
        self.assertEqual(first_name, "(CPLTGL) Centre Pour la Promot")
        self.assertEqual(last_name, "ion de la Liberte D'Expression")

    def test_partial_updates(self):
        self.assertEqual(self.user.profile.country, "US")
        country = "KE"
        username = "george"
        metadata = {"computer": "mac"}
        json_metadata = json.dumps(metadata)
        data = {"username": username, "country": country, "metadata": json_metadata}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.country, country)
        self.assertEqual(profile.metadata, metadata)
        self.assertEqual(profile.user.username, username)

    def test_partial_updates_empty_metadata(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = {}
        profile.save()
        metadata = {"zebra": {"key1": "value1", "key2": "value2"}}
        json_metadata = json.dumps(metadata)
        data = {"metadata": json_metadata, "overwrite": "false"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, metadata)

    def test_partial_updates_too_long(self):
        # the max field length for username is 30 in django
        username = "a" * 31
        data = {"username": username}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"username": ["Ensure this field has no more than 30 characters."]},
        )
        self.assertNotEqual(profile.user.username, username)

    def test_partial_update_metadata_field(self):
        metadata = {"zebra": {"key1": "value1", "key2": "value2"}}
        json_metadata = json.dumps(metadata)
        data = {
            "metadata": json_metadata,
        }
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, metadata)

        # create a new key/value object if it doesn't exist
        data = {"metadata": '{"zebra": {"key3": "value3"}}', "overwrite": "false"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata,
            {"zebra": {"key1": "value1", "key2": "value2", "key3": "value3"}},
        )

        # update an existing key/value object
        data = {"metadata": '{"zebra": {"key2": "second"}}', "overwrite": "false"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata,
            {"zebra": {"key1": "value1", "key2": "second", "key3": "value3"}},
        )

        # add a new key/value object if the key doesn't exist
        data = {"metadata": '{"animal": "donkey"}', "overwrite": "false"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            profile.metadata,
            {
                "zebra": {"key1": "value1", "key2": "second", "key3": "value3"},
                "animal": "donkey",
            },
        )

        # don't pass overwrite param
        data = {"metadata": '{"b": "caah"}'}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, {"b": "caah"})

        # pass 'overwrite' param whose value isn't false
        data = {"metadata": '{"b": "caah"}', "overwrite": "falsey"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, {"b": "caah"})

    def test_put_update(self):

        data = _profile_data()
        # create profile
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # edit username with existing different user's username
        data["username"] = "bob"
        request = self.factory.put(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, user="deno")
        self.assertEqual(response.status_code, 400)

        # update
        data["username"] = "roger"
        data["city"] = "Nairobi"
        request = self.factory.put(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, user="deno")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["city"], data["city"])

    def test_profile_create_mixed_case(self):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        del data["password"]
        profile = UserProfile.objects.get(user__username=data["username"].lower())
        data["id"] = profile.user.pk
        data["gravatar"] = str(profile.gravatar)
        data["url"] = "http://testserver/api/v1/profiles/deno"
        data["user"] = "http://testserver/api/v1/users/deno"
        data["username"] = "deno"
        data["metadata"] = {}
        data["metadata"]["last_password_edit"] = profile.metadata["last_password_edit"]
        data["joined_on"] = profile.user.date_joined
        self.assertEqual(response.data, data)

        data["username"] = "deno"
        data["joined_on"] = str(profile.user.date_joined)
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("%s already exists" % data["username"], response.data["username"])

    def test_change_password(self):
        view = UserProfileViewSet.as_view({"post": "change_password"})
        current_password = "bobbob"
        new_password = "bobbob1"
        old_token = Token.objects.get(user=self.user).key
        post_data = {"current_password": current_password, "new_password": new_password}

        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, user="bob")
        now = timezone.now().isoformat()
        user = User.objects.get(username__iexact=self.user.username)
        user_profile = UserProfile.objects.get(user_id=user.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            type(parse_datetime(user_profile.metadata["last_password_edit"])),
            type(parse_datetime(now)),
        )
        self.assertTrue(user.check_password(new_password))
        self.assertIn("access_token", response.data)
        self.assertIn("temp_token", response.data)
        self.assertEqual(response.data["username"], self.user.username)
        self.assertNotEqual(response.data["access_token"], old_token)

        # Assert requests made with the old tokens are rejected
        post_data = {"current_password": new_password, "new_password": "random"}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, user="bob")
        self.assertEqual(response.status_code, 401)

    def test_change_password_wrong_current_password(self):
        view = UserProfileViewSet.as_view({"post": "change_password"})
        current_password = "wrong_pass"
        new_password = "bobbob1"
        post_data = {"current_password": current_password, "new_password": new_password}

        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, user="bob")
        user = User.objects.get(username__iexact=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"error": "Invalid password. You have 9 attempts left."}
        )
        self.assertFalse(user.check_password(new_password))

    def test_profile_create_with_name(self):
        data = {
            "username": "deno",
            "name": "Dennis deno",
            "email": "deno@columbia.edu",
            "city": "Denoville",
            "country": "US",
            "organization": "Dono Inc.",
            "website": "deno.com",
            "twitter": "denoerama",
            "require_auth": False,
            "password": "denodeno",
            "is_org": False,
        }
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 201)
        del data["password"]
        profile = UserProfile.objects.get(user__username=data["username"])
        data["id"] = profile.user.pk
        data["first_name"] = "Dennis"
        data["last_name"] = "deno"
        data["gravatar"] = profile.gravatar
        data["url"] = "http://testserver/api/v1/profiles/deno"
        data["user"] = "http://testserver/api/v1/users/deno"
        data["metadata"] = {}
        data["metadata"]["last_password_edit"] = profile.metadata["last_password_edit"]
        data["joined_on"] = profile.user.date_joined

        self.assertEqual(response.data, data)

        user = User.objects.get(username="deno")
        self.assertTrue(user.is_active)

    def test_twitter_username_validation(self):
        data = {
            "username": "deno",
            "name": "Dennis deno",
            "email": "deno@columbia.edu",
            "city": "Denoville",
            "country": "US",
            "organization": "Dono Inc.",
            "website": "deno.com",
            "twitter": "denoerama",
            "require_auth": False,
            "password": "denodeno",
            "is_org": False,
        }
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 201)
        data["twitter"] = "denoerama"
        data = {
            "username": "deno",
            "name": "Dennis deno",
            "email": "deno@columbia.edu",
            "city": "Denoville",
            "country": "US",
            "organization": "Dono Inc.",
            "website": "deno.com",
            "twitter": "denoeramaddfsdsl8729320392ujijdswkp--22kwklskdsjs",
            "require_auth": False,
            "password": "denodeno",
            "is_org": False,
        }
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["twitter"],
            ["Invalid twitter username {}".format(data["twitter"])],
        )

        user = User.objects.get(username="deno")
        self.assertTrue(user.is_active)

    def test_put_patch_method_on_names(self):
        data = _profile_data()
        # create profile
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # update
        data["first_name"] = "Tom"
        del data["name"]
        request = self.factory.put(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )

        response = self.view(request, user="deno")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], data["first_name"])

        first_name = "Henry"
        last_name = "Thierry"

        data = {"first_name": first_name, "last_name": last_name}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["first_name"], data["first_name"])
        self.assertEqual(response.data["last_name"], data["last_name"])

    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_send_email_activation_api(self, mock_send_mail):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data["name"]
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        # Activation email not sent
        self.assertFalse(mock_send_mail.called)
        user = User.objects.get(username="deno")
        self.assertTrue(user.is_active)

    def test_partial_update_without_password_fails(self):
        data = {"email": "user@example.com"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            ["Your password is required when updating your email address."],
            response.data,
        )

    def test_partial_update_with_invalid_email_fails(self):
        data = {"email": "user@example"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user=self.user.username)
        self.assertEqual(response.status_code, 400)

    @patch(
        (
            "onadata.libs.serializers.user_profile_serializer."
            "send_verification_email.delay"
        )
    )
    def test_partial_update_email(self, mock_send_verification_email):
        profile_data = _profile_data()
        self._create_user_using_profiles_endpoint(profile_data)

        rp = RegistrationProfile.objects.get(
            user__username=profile_data.get("username")
        )
        deno_extra = {"HTTP_AUTHORIZATION": "Token %s" % rp.user.auth_token}

        data = {"email": "user@example.com", "password": "invalid_password"}
        request = self.factory.patch("/", data=data, **deno_extra)
        response = self.view(request, user=profile_data.get("username"))
        self.assertEqual(response.status_code, 400)

        data = {"email": "user@example.com", "password": profile_data.get("password")}
        request = self.factory.patch("/", data=data, **deno_extra)
        response = self.view(request, user=profile_data.get("username"))
        profile = UserProfile.objects.get(user=rp.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.user.email, "user@example.com")

        rp = RegistrationProfile.objects.get(
            user__username=profile_data.get("username")
        )
        self.assertIn("is_email_verified", rp.user.profile.metadata)
        self.assertFalse(rp.user.profile.metadata.get("is_email_verified"))
        self.assertTrue(mock_send_verification_email.called)

    def test_update_first_last_name_password_not_affected(self):
        data = {"first_name": "update_first", "last_name": "update_last"}
        request = self.factory.patch(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, user=self.user.username)

        self.assertEqual(response.status_code, 200)

        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )

        auth = DigestAuth("bob@columbia.edu", "bobbob")
        request = self._get_request_session_with_auth(view, auth)

        response = view(request)
        self.assertEqual(response.status_code, 200)

    @patch(
        (
            "onadata.libs.serializers.user_profile_serializer."
            "send_verification_email.delay"
        )
    )
    def test_partial_update_unique_email_api(self, mock_send_verification_email):
        profile_data = {
            "username": "bobby",
            "first_name": "Bob",
            "last_name": "Blender",
            "email": "bobby@columbia.edu",
            "city": "Bobville",
            "country": "US",
            "organization": "Bob Inc.",
            "website": "bob.com",
            "twitter": "boberama",
            "require_auth": False,
            "password": "bobbob",
            "is_org": False,
            "name": "Bob Blender",
        }
        self._create_user_using_profiles_endpoint(profile_data)

        rp = RegistrationProfile.objects.get(
            user__username=profile_data.get("username")
        )
        deno_extra = {"HTTP_AUTHORIZATION": "Token %s" % rp.user.auth_token}

        data = {"email": "example@gmail.com", "password": profile_data.get("password")}
        request = self.factory.patch(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **deno_extra
        )
        response = self.view(request, user=rp.user.username)

        self.assertEqual(response.status_code, 200)

        rp = RegistrationProfile.objects.get(
            user__username=profile_data.get("username")
        )
        self.assertIn("is_email_verified", rp.user.profile.metadata)
        self.assertFalse(rp.user.profile.metadata.get("is_email_verified"))
        self.assertTrue(mock_send_verification_email.called)

        self.assertEqual(response.data["email"], data["email"])
        # create User
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(_profile_data()),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="deno")
        # Update email
        request = self.factory.patch(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, user=user.username)

        self.assertEqual(response.status_code, 400)

    def test_profile_create_fails_with_long_first_and_last_names(self):
        data = {
            "username": "machicimo",
            "email": "mike@columbia.edu",
            "city": "Denoville",
            "country": "US",
            "last_name": "undeomnisistenatuserrorsitvoluptatem",
            "first_name": "quirationevoluptatemsequinesciunt",
        }
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(
            response.data["first_name"][0],
            "Ensure this field has no more than 30 characters.",
        )
        self.assertEqual(
            response.data["last_name"][0],
            "Ensure this field has no more than 30 characters.",
        )
        self.assertEqual(response.status_code, 400)

    @all_requests
    def grant_perms_form_builder(
        self, url, request
    ):  # pylint: disable=no-self-use,unused-argument

        assert "X-ONADATA-KOBOCAT-AUTH" in request.headers

        response = requests.Response()
        response.status_code = 201
        setattr(
            response,
            "_content",
            {"detail": "Successfully granted default model level perms to user."},
        )
        return response

    def test_create_user_with_given_name(self):
        registered_functions = [r[1]() for r in signals.post_save.receivers]
        self.assertIn(set_kpi_formbuilder_permissions, registered_functions)
        with HTTMock(self.grant_perms_form_builder):
            with self.settings(KPI_FORMBUILDER_URL="http://test_formbuilder$"):
                extra_data = {"username": "rust"}
                self._login_user_and_profile(extra_post_data=extra_data)

    def test_get_monthly_submissions(self):
        """
        Test getting monthly submissions for a user
        """
        view = UserProfileViewSet.as_view({"get": "monthly_submissions"})
        # publish form and make submissions
        self._publish_xls_form_to_project()
        self._make_submissions()
        count1 = Instance.objects.filter(xform=self.xform).count()

        request = self.factory.get("/", **self.extra)
        response = view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.xform.shared)
        self.assertEqual(response.data, {"private": count1})

        # publish another form, make submission and make it public
        self._publish_form_with_hxl_support()
        self.assertEqual(self.xform.id_string, "hxl_example")
        count2 = (
            Instance.objects.filter(xform=self.xform)
            .filter(date_created__year=datetime.datetime.now().year)
            .filter(date_created__month=datetime.datetime.now().month)
            .filter(date_created__day=datetime.datetime.now().day)
            .count()
        )

        self.xform.shared = True
        self.xform.save()
        request = self.factory.get("/", **self.extra)
        response = view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"private": count1, "public": count2})

    def test_get_monthly_submissions_with_year_and_month_params(self):
        """
        Test passing both month and year params
        """
        view = UserProfileViewSet.as_view({"get": "monthly_submissions"})
        # publish form and make a submission dated 2013-02-18
        self._publish_xls_form_to_project()
        survey = self.surveys[0]
        submission_time = parse_datetime("2013-02-18 15:54:01Z")
        self._make_submission(
            os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                survey,
                survey + ".xml",
            ),
            forced_submission_time=submission_time,
        )
        count = (
            Instance.objects.filter(xform=self.xform)
            .filter(date_created__month=2)
            .filter(date_created__year=2013)
            .count()
        )

        # get submission count and assert the response is correct
        data = {"month": 2, "year": 2013}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.xform.shared)
        self.assertEqual(response.data, {"private": count})

    def test_monthly_submissions_with_month_param(self):
        """
        Test that by passing only the value for month,
        the year is assumed to be the current year
        """
        view = UserProfileViewSet.as_view({"get": "monthly_submissions"})
        month = datetime.datetime.now().month
        year = datetime.datetime.now().year

        # publish form and make submissions
        self._publish_xls_form_to_project()
        self._make_submissions()
        count = (
            Instance.objects.filter(xform=self.xform)
            .filter(date_created__year=year)
            .filter(date_created__month=month)
            .count()
        )

        data = {"month": month}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.xform.shared)
        self.assertEqual(response.data, {"private": count})

    def test_monthly_submissions_with_year_param(self):
        """
        Test that by passing only the value for year
        the month is assumed to be the current month
        """
        view = UserProfileViewSet.as_view({"get": "monthly_submissions"})
        month = datetime.datetime.now().month

        # publish form and make submissions dated the year 2013
        # and the current month
        self._publish_xls_form_to_project()
        survey = self.surveys[0]
        _time = parse_datetime("2013-" + str(month) + "-18 15:54:01Z")
        self._make_submission(
            os.path.join(
                self.main_directory,
                "fixtures",
                "transportation",
                "instances",
                survey,
                survey + ".xml",
            ),
            forced_submission_time=_time,
        )
        count = (
            Instance.objects.filter(xform=self.xform)
            .filter(date_created__year=2013)
            .filter(date_created__month=month)
            .count()
        )

        data = {"year": 2013}
        request = self.factory.get("/", data=data, **self.extra)
        response = view(request, user=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.xform.shared)
        self.assertEqual(response.data, {"private": count})

    @override_settings(ENABLE_EMAIL_VERIFICATION=True)
    @patch("onadata.apps.api.viewsets.user_profile_viewset.RegistrationProfile")
    def test_reads_from_master(self, mock_rp_class):
        """
        Test that on failure to retrieve a UserProfile in the first
        try a second query is run on the master database
        """
        data = _profile_data()
        self._create_user_using_profiles_endpoint(data)

        view = UserProfileViewSet.as_view({"get": "verify_email"})
        rp = RegistrationProfile.objects.get(user__username=data.get("username"))
        _data = {"verification_key": rp.activation_key}
        mock_rp_class.DoesNotExist = RegistrationProfile.DoesNotExist
        mock_rp_class.objects.select_related(
            "user", "user__profile"
        ).get.side_effect = [RegistrationProfile.DoesNotExist, rp]
        request = self.factory.get("/", data=_data)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_email_verified", response.data)
        self.assertIn("username", response.data)
        self.assertTrue(response.data.get("is_email_verified"))
        self.assertEqual(response.data.get("username"), data.get("username"))
        self.assertEqual(
            mock_rp_class.objects.select_related(
                "user", "user__profile"
            ).get.call_count,
            2,
        )

    def test_change_password_attempts(self):
        view = UserProfileViewSet.as_view({"post": "change_password"})

        # clear cache
        cache.delete("change_password_attempts-bob")
        cache.delete("lockout_change_password_user-bob")
        self.assertIsNone(cache.get("change_password_attempts-bob"))
        self.assertIsNone(cache.get("lockout_change_password_user-bob"))

        # first attempt
        current_password = "wrong_pass"
        new_password = "bobbob1"
        post_data = {"current_password": current_password, "new_password": new_password}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, user="bob")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"error": "Invalid password. You have 9 attempts left."}
        )
        self.assertEqual(cache.get("change_password_attempts-bob"), 1)

        # second attempt
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, user="bob")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"error": "Invalid password. You have 8 attempts left."}
        )
        self.assertEqual(cache.get("change_password_attempts-bob"), 2)

        # check user is locked out
        request = self.factory.post("/", data=post_data, **self.extra)
        cache.set("change_password_attempts-bob", 9)
        self.assertIsNone(cache.get("lockout_change_password_user-bob"))
        response = view(request, user="bob")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"error": "Too many password reset attempts. Try again in 30 minutes"},
        )
        self.assertEqual(cache.get("change_password_attempts-bob"), 10)
        self.assertIsNotNone(cache.get("lockout_change_password_user-bob"))
        lockout = datetime.datetime.strptime(
            cache.get("lockout_change_password_user-bob"), "%Y-%m-%dT%H:%M:%S"
        )
        self.assertIsInstance(lockout, datetime.datetime)

        # clear cache
        cache.delete("change_password_attempts-bob")
        cache.delete("lockout_change_password_user-bob")

    @patch("onadata.apps.main.signals.send_generic_email")
    @override_settings(ENABLE_ACCOUNT_ACTIVATION_EMAILS=True)
    def test_account_activation_emails(self, mock_send_mail):
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = _profile_data()
        del data["name"]
        request = self.factory.post(
            "/api/v1/profiles",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        # Account notification email sent
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(mock_send_mail.call_count, 2)

        mock_send_mail.assert_has_calls(
            [
                call(
                    data["email"],
                    "\nHi deno,\n\nYour account has been "
                    "successfully created! Kindly wait till an "
                    "administrator activates your account."
                    "\n\nThank you for choosing Ona!\n"
                    "Please contact us with any questions, "
                    "we're always happy to help."
                    "\n\nThanks,\nThe Team at Ona",
                    "Ona account created - Pending activation",
                ),
                call(
                    data["email"],
                    "\nHi deno,\n\nYour account has been activated."
                    "\n\nThank you for choosing Ona!"
                    "\n\nThanks,\nThe Team at Ona",
                    "Ona account activated",
                ),
            ]
        )
