# -*- coding: utf-8 -*-
"""
Test /user API endpoint
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.timezone import now

from django_digest.backend.db import update_partial_digests
from django_digest.test import BasicAuth, DigestAuth
from rest_framework import authentication
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.serializers.password_reset_serializer import default_token_generator
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.utils.cache_tools import safe_key


class TestConnectViewSet(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = ConnectViewSet.as_view(
            {
                "get": "list",
                "post": "reset",
                "delete": "expire",
            }
        )
        self.data = {
            "url": "http://testserver/api/v1/profiles/bob",
            "username": "bob",
            "name": "Bob",
            "email": "bob@columbia.edu",
            "city": "Bobville",
            "country": "US",
            "organization": "Bob Inc.",
            "website": "bob.com",
            "twitter": "boberama",
            "gravatar": self.user.profile.gravatar,
            "require_auth": False,
            "user": "http://testserver/api/v1/users/bob",
            "api_token": self.user.auth_token.key,
        }

    def test_generate_auth_token(self):
        self.view = ConnectViewSet.as_view(
            {
                "post": "create",
            }
        )
        request = self.factory.post("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

    def test_regenerate_auth_token(self):
        self.view = ConnectViewSet.as_view(
            {
                "get": "regenerate_auth_token",
            }
        )
        prev_token = self.user.auth_token
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        new_token = Token.objects.get(user=self.user)
        self.assertNotEqual(prev_token, new_token)

        self.view = ConnectViewSet.as_view(
            {
                "get": "list",
            }
        )
        self.extra = {"HTTP_AUTHORIZATION": "Token %s" % new_token}
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        self.extra = {"HTTP_AUTHORIZATION": "Token invalidtoken"}
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["www-authenticate"], "Token")

    def test_get_profile(self):
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = TempToken.objects.get(user__username="bob")
        self.data["temp_token"] = temp_token.key
        self.assertEqual(response.status_code, 200)
        self.assertEqual(dict(response.data), self.data)

    def test_get_profile_user_no_auth_token(self):
        """
        Test new user auth token is generated when user doesn't have an
        existing one
        """
        # delete auth token
        token = Token.objects.get(user=self.user)
        old_token_key = token.key
        token.delete()

        view = ConnectViewSet.as_view(
            {"get": "list"},
            authentication_classes=(
                DigestAuthentication,
                authentication.BasicAuthentication,
            ),
        )
        request = self.factory.get("/")
        auth = BasicAuth("bob", "bobbob")
        request.META.update(auth(request.META))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data.get("api_token"), old_token_key)

    def test_using_valid_temp_token(self):
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = response.data["temp_token"]

        self.extra = {"HTTP_AUTHORIZATION": "TempToken %s" % temp_token}
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(temp_token, response.data["temp_token"])

    def test_using_invalid_temp_token(self):
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = "abcdefghijklmopqrstuvwxyz"

        self.extra = {"HTTP_AUTHORIZATION": "TempToken %s" % temp_token}
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid token")
        self.assertEqual(response["www-authenticate"], "TempToken")

    def test_using_expired_temp_token(self):
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = response.data["temp_token"]
        temp_token_obj = TempToken.objects.get(key=temp_token)

        day = timedelta(seconds=settings.DEFAULT_TEMP_TOKEN_EXPIRY_TIME)
        today = now()
        yesterday = today - day
        temp_token_obj.created = yesterday
        temp_token_obj.save()

        self.extra = {"HTTP_AUTHORIZATION": "TempToken %s" % temp_token_obj.key}
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.data["detail"], "Token expired")

    def test_expire_temp_token_using_expire_endpoint(self):
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = response.data["temp_token"]

        # expire temporary token
        request = self.factory.delete("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 204)

        # try to expire temporary token for the second time
        request = self.factory.delete("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Temporary token not found!")

        # try to login with deleted temporary token
        self.extra = {"HTTP_AUTHORIZATION": "TempToken %s" % temp_token}
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid token")
        self.assertEqual(response["www-authenticate"], "TempToken")

    def test_get_starred_projects(self):
        self._project_create()

        # add star as bob
        view = ProjectViewSet.as_view({"get": "star", "post": "star"})
        request = self.factory.post("/", **self.extra)
        response = view(request, pk=self.project.pk)

        # get starred projects
        view = ConnectViewSet.as_view(
            {
                "get": "starred",
            }
        )
        request = self.factory.get("/", **self.extra)
        response = view(request, user=self.user)

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        request.user = self.user
        self.project_data = ProjectSerializer(
            self.project, context={"request": request}
        ).data
        del self.project_data["date_modified"]
        del response.data[0]["date_modified"]
        self.assertEqual(len(response.data), 1)
        self.assertDictEqual(dict(response.data[0]), dict(self.project_data))

    def test_user_list_with_digest(self):
        # Clear cache
        cache.clear()

        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )
        request = self.factory.head("/")

        auth = DigestAuth("bob", "bob")
        response = view(request)
        self.assertTrue(response.has_header("WWW-Authenticate"))
        self.assertTrue(response["WWW-Authenticate"].startswith("Digest "))
        self.assertIn("nonce=", response["WWW-Authenticate"])
        request = self.factory.get("/")
        request.META.update(auth(request.META, response))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Invalid username/password. For security reasons, "
            "after 9 more failed login attempts you'll "
            "have to wait 30 minutes before trying again.",
        )
        auth = DigestAuth("bob", "bobbob")
        request.META.update(auth(request.META, response))
        request.session = self.client.session

        response = view(request)
        temp_token = TempToken.objects.get(user__username="bob")
        self.data["temp_token"] = temp_token.key
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_user_list_with_basic_and_digest(self):
        view = ConnectViewSet.as_view(
            {"get": "list"},
            authentication_classes=(
                DigestAuthentication,
                authentication.BasicAuthentication,
            ),
        )
        request = self.factory.get("/")
        auth = BasicAuth("bob", "bob")
        request.META.update(auth(request.META))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid username/password.")
        auth = BasicAuth("bob", "bobbob")
        request.META.update(auth(request.META))
        request.session = self.client.session

        response = view(request)
        temp_token = TempToken.objects.get(user__username="bob")
        self.data["temp_token"] = temp_token.key
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    @patch("onadata.libs.serializers.password_reset_serializer.send_mail")
    def test_request_reset_password(self, mock_send_mail):
        data = {
            "email": self.user.email,
            "reset_url": "http://testdomain.com/reset_form",
        }
        request = self.factory.post("/", data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(mock_send_mail.called)

        data["email_subject"] = "X" * 100
        request = self.factory.post("/", data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["email_subject"][0],
            "Ensure this field has no more than 78 characters.",
        )

        mock_send_mail.called = False
        request = self.factory.post("/")
        response = self.view(request)
        self.assertFalse(mock_send_mail.called)
        self.assertEqual(response.status_code, 400)

    def test_reset_user_password(self):
        # set user.last_login, ensures we get same/valid token
        # https://code.djangoproject.com/ticket/10265
        self.user.last_login = now()
        self.user.save()
        token = default_token_generator.make_token(self.user)
        new_password = "bobbob1"
        data = {"token": token, "new_password": new_password}
        # missing uid, should fail
        request = self.factory.post("/", data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

        data["uid"] = urlsafe_base64_encode(force_bytes(self.user.pk))
        # with uid, should be successful
        request = self.factory.post("/", data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email=self.user.email)
        self.assertEqual(user.username, response.data["username"])
        self.assertTrue(user.check_password(new_password))

        request = self.factory.post("/", data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

    def test_reset_user_password_with_updated_user_email(self):
        # set user.last_login, ensures we get same/valid token
        # https://code.djangoproject.com/ticket/10265
        self.user.last_login = now()
        self.user.save()
        new_password = "bobbob1"
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        mhv = default_token_generator
        token = mhv.make_token(self.user)
        data = {"token": token, "new_password": new_password, "uid": uid}
        # check that the token is valid
        valid_token = mhv.check_token(self.user, token)
        self.assertTrue(valid_token)

        # Update user email
        self.user.email = "bob2@columbia.edu"
        self.user.save()
        update_partial_digests(self.user, "bobbob")

        # Token should be invalid as the email was updated
        invalid_token = mhv.check_token(self.user, token)
        self.assertFalse(invalid_token)

        request = self.factory.post("/", data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertTrue("Invalid token" in response.data["non_field_errors"][0])

    @patch("onadata.libs.serializers.password_reset_serializer.send_mail")
    def test_request_reset_password_custom_email_subject(self, mock_send_mail):
        data = {
            "email": self.user.email,
            "reset_url": "http://testdomain.com/reset_form",
            "email_subject": "You requested for a reset password",
        }
        request = self.factory.post("/", data=data)
        response = self.view(request)

        self.assertTrue(mock_send_mail.called)
        self.assertEqual(response.status_code, 204)

    def test_user_updates_email_wrong_password(self):
        # Clear cache
        cache.clear()
        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )

        auth = DigestAuth("bob@columbia.edu", "bob")
        request = self._get_request_session_with_auth(view, auth)

        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Invalid username/password. For security reasons, "
            "after 9 more failed login attempts you'll have to "
            "wait 30 minutes before trying again.",
        )

    def test_user_updates_email(self):
        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )

        auth = DigestAuth("bob@columbia.edu", "bobbob")
        request = self._get_request_session_with_auth(view, auth)

        response = view(request)
        temp_token = TempToken.objects.get(user__username="bob")
        self.data["temp_token"] = temp_token.key
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

        self.user.email = "bob2@columbia.edu"
        self.user.save()
        update_partial_digests(self.user, "bobbob")

        auth = DigestAuth("bob2@columbia.edu", "bobbob")
        request = self._get_request_session_with_auth(view, auth)

        response = view(request)
        temp_token = TempToken.objects.get(user__username="bob")
        self.data["temp_token"] = temp_token.key
        self.data["email"] = "bob2@columbia.edu"
        self.assertEqual(response.status_code, 200)

    def test_user_has_no_profile_bug(self):
        alice = User.objects.create(username="alice")
        alice.set_password("alice")
        update_partial_digests(alice, "alice")
        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )

        auth = DigestAuth("alice", "alice")
        request = self._get_request_session_with_auth(view, auth)

        response = view(request)
        self.assertEqual(response.status_code, 200)

    @patch("onadata.apps.api.tasks.send_account_lockout_email.apply_async")
    def test_login_attempts(self, send_account_lockout_email):
        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )
        auth = DigestAuth("bob", "bob")
        # clear cache
        cache.clear()

        request = self._get_request_session_with_auth(view, auth)

        # first time it creates a cache
        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Invalid username/password. For security reasons, "
            "after 9 more failed login attempts you'll have to "
            "wait 30 minutes before trying again.",
        )
        request_ip = request.META.get("REMOTE_ADDR")
        self.assertEqual(cache.get(safe_key(f"login_attempts-{request_ip}-bob")), 1)

        # cache value increments with subsequent attempts
        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Invalid username/password. For security reasons, "
            "after 8 more failed login attempts you'll have to "
            "wait 30 minutes before trying again.",
        )
        self.assertEqual(cache.get(safe_key(f"login_attempts-{request_ip}-bob")), 2)

        request = self._get_request_session_with_auth(
            view, auth, extra={"HTTP_X_REAL_IP": "5.6.7.8"}
        )
        # login attempts are tracked separately for other IPs
        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(cache.get(safe_key(f"login_attempts-{request_ip}-bob")), 2)
        self.assertEqual(cache.get(safe_key("login_attempts-5.6.7.8-bob")), 1)

        # login_attempts doesn't increase with correct login
        auth = DigestAuth("bob", "bobbob")
        request = self._get_request_session_with_auth(view, auth)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cache.get(safe_key(f"login_attempts-{request_ip}-bob")), 2)

        # lockout_user cache created upon fifth attempt
        auth = DigestAuth("bob", "bob")
        request = self._get_request_session_with_auth(view, auth)
        self.assertFalse(send_account_lockout_email.called)
        cache.set(safe_key(f"login_attempts-{request_ip}-bob"), 9)
        self.assertIsNone(cache.get(safe_key(f"lockout_ip-{request_ip}-bob")))
        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Locked out. Too many wrong username/password "
            "attempts. Try again in 30 minutes.",
        )
        self.assertEqual(cache.get(safe_key(f"login_attempts-{request_ip}-bob")), 10)
        self.assertIsNotNone(cache.get(safe_key(f"lockout_ip-{request_ip}-bob")))
        lockout = datetime.strptime(
            cache.get(safe_key(f"lockout_ip-{request_ip}-bob")), "%Y-%m-%dT%H:%M:%S"
        )
        self.assertIsInstance(lockout, datetime)

        # email sent upon limit being reached with right arguments
        subject_path = "account_lockout/lockout_email_subject.txt"
        self.assertTrue(send_account_lockout_email.called)
        email_subject = render_to_string(subject_path)
        self.assertIn(email_subject, send_account_lockout_email.call_args[1]["args"])
        self.assertEqual(send_account_lockout_email.call_count, 2, "Called twice")

        # subsequent login fails after lockout even with correct credentials
        auth = DigestAuth("bob", "bobbob")
        request = self._get_request_session_with_auth(view, auth)
        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Locked out. Too many wrong username/password "
            "attempts. Try again in 30 minutes.",
        )

        # Other users on same IP not locked out
        alice = User.objects.create(username="alice")
        alice.set_password("alice")
        update_partial_digests(alice, "alice")
        auth = DigestAuth("alice", "alice")

        request = self._get_request_session_with_auth(view, auth)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.META.get("REMOTE_ADDR"), request_ip)
        # clear cache
        cache.clear()

    def test_generate_odk_token(self):
        """
        Test that ODK Tokens can be created
        """
        view = ConnectViewSet.as_view({"post": "odk_token"})
        request = self.factory.post("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 201)

    def test_regenerate_odk_token(self):
        """
        Test that ODK Tokens can be regenerated and old tokens
        are set to Inactive after regeneration
        """
        view = ConnectViewSet.as_view({"post": "odk_token"})
        request = self.factory.post("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 201)
        old_token = response.data["odk_token"]

        with self.assertRaises(ODKToken.DoesNotExist):
            ODKToken.objects.get(user=self.user, status=ODKToken.INACTIVE)

        request = self.factory.post("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data["odk_token"], old_token)

        # Test that the previous token was set to inactive
        inactive_token = ODKToken.objects.get(user=self.user, status=ODKToken.INACTIVE)
        self.assertEqual(inactive_token.raw_key, old_token)

    def test_retrieve_odk_token(self):
        """
        Test that ODK Tokens can be retrieved
        """
        view = ConnectViewSet.as_view({"post": "odk_token", "get": "odk_token"})
        request = self.factory.post("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 201)
        odk_token = response.data["odk_token"]
        expires = response.data["expires"]

        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["odk_token"], odk_token)
        self.assertEqual(response.data["expires"], expires)

    def test_deactivate_token_when_expires_is_None(self):
        """
        Test that when a token's .expires field is nil, it will be deactivated
        and a new one created in it's place
        """
        view = ConnectViewSet.as_view({"post": "odk_token", "get": "odk_token"})

        # Create an active tokens
        token = ODKToken.objects.create(user=self.user)
        ODKToken.objects.filter(pk=token.pk).update(expires=None)

        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(ODKToken.objects.filter(status=ODKToken.ACTIVE)), 1)
        self.assertNotEqual(response.data["odk_token"], token.raw_key)

    def test_deactivates_multiple_active_odk_token(self):
        """
        Test that the viewset deactivates tokens when two or more are
        active at the same time and returns a new token
        """
        view = ConnectViewSet.as_view({"post": "odk_token", "get": "odk_token"})

        # Create two active tokens
        token_1 = ODKToken.objects.create(user=self.user)
        token_2 = ODKToken.objects.create(user=self.user)

        self.assertEqual(token_1.status, ODKToken.ACTIVE)
        self.assertEqual(token_2.status, ODKToken.ACTIVE)

        # Test that the GET request deactivates the two active tokens
        # and returns a new active token
        request = self.factory.get("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(ODKToken.objects.filter(status=ODKToken.ACTIVE)), 1)
        self.assertNotEqual(response.data["odk_token"], token_1.raw_key)
        self.assertNotEqual(response.data["odk_token"], token_2.raw_key)

        token_1 = ODKToken.objects.get(pk=token_1.pk)
        token_2 = ODKToken.objects.get(pk=token_2.pk)
        token_3_key = response.data["odk_token"]

        self.assertEqual(token_1.status, ODKToken.INACTIVE)
        self.assertEqual(token_2.status, ODKToken.INACTIVE)

        # Test that the POST request deactivates two active tokens and returns
        # a new active token

        token_1.status = ODKToken.ACTIVE
        token_1.save()

        self.assertEqual(len(ODKToken.objects.filter(status=ODKToken.ACTIVE)), 2)
        request = self.factory.post("/", **self.extra)
        request.session = self.client.session
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(ODKToken.objects.filter(status=ODKToken.ACTIVE)), 1)
        self.assertNotEqual(response.data["odk_token"], token_1.raw_key)
        self.assertNotEqual(response.data["odk_token"], token_3_key)
