"""
Tests that the OAuth2 password grant is gone from every route that could
issue or renew a token through it.
"""

from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, RefreshToken, get_application_model

from onadata.libs.authentication import MasterReplicaOAuth2Validator

CLIENT_SECRET = "client-secret"
PASSWORD = "correct-password"


class PasswordGrantRemovedTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="bob", email="bob@example.com", password=PASSWORD
        )
        self.application_model = get_application_model()

    def _application(self, grant_type):
        return self.application_model.objects.create(
            name=f"{grant_type}-app",
            user=self.user,
            client_id=f"{grant_type}-client",
            client_secret=CLIENT_SECRET,
            client_type=self.application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=grant_type,
            redirect_uris="https://app.example/callback",
        )

    def _password_grant(self, password):
        application = self._application(self.application_model.GRANT_PASSWORD)
        return self.client.post(
            "/o/token/",
            {
                "grant_type": "password",
                "username": self.user.username,
                "password": password,
                "client_id": application.client_id,
                "client_secret": CLIENT_SECRET,
            },
        )

    def _refresh(self, application):
        access_token = AccessToken.objects.create(
            user=self.user,
            application=application,
            token=f"access-{application.pk}",
            expires=timezone.now() + timedelta(hours=1),
            scope="read",
        )
        refresh_token = RefreshToken.objects.create(
            user=self.user,
            application=application,
            token=f"refresh-{application.pk}",
            access_token=access_token,
        )
        return self.client.post(
            "/o/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token.token,
                "client_id": application.client_id,
                "client_secret": CLIENT_SECRET,
            },
        )

    def test_the_password_grant_is_refused_with_the_right_password(self):
        self.assertTrue(self.user.check_password(PASSWORD))

        response = self._password_grant(PASSWORD)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "unsupported_grant_type")
        self.assertFalse(AccessToken.objects.exists())

    def test_a_wrong_password_gets_the_same_answer_as_the_right_one(self):
        """The grant is refused before the password is checked, so the
        endpoint cannot be used to test passwords."""
        right = self._password_grant(PASSWORD)
        self.application_model.objects.all().delete()
        wrong = self._password_grant("wrong-password")

        self.assertEqual(wrong.status_code, right.status_code)
        self.assertEqual(wrong.json(), right.json())

    def test_the_password_grant_in_the_query_string_issues_no_token(self):
        """oauthlib refuses query parameters on a POST before it picks a
        grant, so this route stays closed even past the view's check."""
        application = self._application(self.application_model.GRANT_PASSWORD)

        response = self.client.post(
            "/o/token/?grant_type=password",
            {
                "username": self.user.username,
                "password": PASSWORD,
                "client_id": application.client_id,
                "client_secret": CLIENT_SECRET,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access_token", response.json())
        self.assertFalse(AccessToken.objects.filter(user=self.user).exists())

    def test_a_password_grant_application_cannot_renew_its_tokens(self):
        """A refresh token issued through the password grant never expires by
        default. Its application is refused every grant, so the token is
        dead too."""
        response = self._refresh(
            self._application(self.application_model.GRANT_PASSWORD)
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "unauthorized_client")

    def test_other_applications_still_renew_their_tokens(self):
        """The refusal is tied to the password grant, not to refreshing."""
        response = self._refresh(
            self._application(self.application_model.GRANT_AUTHORIZATION_CODE)
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("access_token", response.json())

    def test_the_validator_never_accepts_a_password(self):
        """A backstop for any route into oauthlib other than /o/token/."""
        self.assertTrue(self.user.check_password(PASSWORD))
        validator = MasterReplicaOAuth2Validator()
        application = self._application(self.application_model.GRANT_PASSWORD)

        accepted = validator.validate_user(
            self.user.username,
            PASSWORD,
            application,
            SimpleNamespace(client=application),
        )

        self.assertFalse(accepted)


class ApplicationFormsTestCase(TestCase):
    """The registration and update forms no longer offer the password grant."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )
        self.client.force_login(self.user)
        self.application_model = get_application_model()

    def _grant_choices(self, response):
        self.assertEqual(response.status_code, 200)
        field = response.context["form"].fields["authorization_grant_type"]
        return [value for value, _label in field.choices]

    def test_registration_offers_every_grant_but_password(self):
        choices = self._grant_choices(self.client.get("/o/applications/register/"))

        self.assertIn(self.application_model.GRANT_AUTHORIZATION_CODE, choices)
        self.assertNotIn(self.application_model.GRANT_PASSWORD, choices)

    def _form(self, grant_type, **overrides):
        return {
            "name": f"{grant_type}-app",
            "client_id": f"{grant_type}-client",
            "client_secret": "client-secret",
            "client_type": self.application_model.CLIENT_CONFIDENTIAL,
            "authorization_grant_type": grant_type,
            "redirect_uris": "https://app.example/callback",
            "post_logout_redirect_uris": "",
            "allowed_origins": "",
            "algorithm": "",
            **overrides,
        }

    def test_registering_a_password_grant_application_is_refused(self):
        """The same form registers a code application, so the grant type is
        the only thing wrong with the refused one."""
        code = self.application_model.GRANT_AUTHORIZATION_CODE
        password = self.application_model.GRANT_PASSWORD

        registered = self.client.post("/o/applications/register/", self._form(code))
        refused = self.client.post("/o/applications/register/", self._form(password))

        self.assertEqual(
            registered.status_code,
            302,
            registered.context and registered.context["form"].errors,
        )
        self.assertEqual(refused.status_code, 200)
        self.assertEqual(
            set(refused.context["form"].errors), {"authorization_grant_type"}
        )
        self.assertEqual(
            list(
                self.application_model.objects.values_list(
                    "authorization_grant_type", flat=True
                )
            ),
            [code],
        )

    def test_a_password_grant_application_keeps_its_grant_type(self):
        """Switching it to another grant would let its old refresh tokens be
        renewed again, so the field is locked while the rest stays editable."""
        application = self.application_model.objects.create(
            name="password-app",
            user=self.user,
            client_type=self.application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=self.application_model.GRANT_PASSWORD,
        )
        url = f"/o/applications/{application.pk}/update/"
        form = self.client.get(url).context["form"]
        self.assertTrue(form.fields["authorization_grant_type"].disabled)

        response = self.client.post(
            url,
            self._form(
                self.application_model.GRANT_AUTHORIZATION_CODE,
                name="renamed",
                client_id=application.client_id,
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
            response.context and response.context["form"].errors,
        )
        application.refresh_from_db()
        self.assertEqual(application.name, "renamed")
        self.assertEqual(
            application.authorization_grant_type,
            self.application_model.GRANT_PASSWORD,
        )

    def test_editing_an_application_offers_every_grant_but_password(self):
        application = self.application_model.objects.create(
            name="code-app",
            user=self.user,
            client_type=self.application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=self.application_model.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://app.example/callback",
        )

        choices = self._grant_choices(
            self.client.get(f"/o/applications/{application.pk}/update/")
        )

        self.assertIn(self.application_model.GRANT_AUTHORIZATION_CODE, choices)
        self.assertNotIn(self.application_model.GRANT_PASSWORD, choices)
