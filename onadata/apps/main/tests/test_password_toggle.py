"""Every page with a password input loads the script that adds a reveal button."""

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

SCRIPT = "js/password-toggle.js"
PASSWORD_INPUT = 'type="password"'


class TestPasswordToggleScript(TestCase):
    def _render(self, template_name):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        return render_to_string(template_name, request=request)

    def test_base_loads_the_script(self):
        self.assertIn(SCRIPT, self._render("base.html"))

    def test_ona_base_loads_the_script(self):
        self.assertIn(SCRIPT, self._render("ona_base.html"))

    def test_password_change_page_loads_the_script(self):
        user = User.objects.create_user(username="bob", password="bob-pass-123")
        self.client.force_login(user)

        response = self.client.get(reverse("auth_password_change"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, PASSWORD_INPUT)
        self.assertContains(response, SCRIPT)

    def test_sign_in_page_loads_the_script(self):
        response = self.client.get(reverse("two_factor:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "two_factor/core/login.html")
        self.assertContains(response, PASSWORD_INPUT)
        self.assertContains(response, SCRIPT, count=1)


class TestPasswordToggleSource(SimpleTestCase):
    """Guards on the script's source, since CI runs no JavaScript.

    They fail when a guarantee is deleted, not when its behaviour regresses.
    """

    def setUp(self):
        path = finders.find(SCRIPT)
        self.assertIsNotNone(path)
        with open(path, encoding="utf-8") as script:
            self.source = script.read()

    def test_labels_are_extractable_for_translation(self):
        self.assertIn('gettext("Show password")', self.source)
        self.assertIn('gettext("Hide password")', self.source)

    def test_label_follows_the_state_without_aria_pressed(self):
        self.assertIn(
            'button.setAttribute("aria-label", revealed ? HIDE_LABEL : SHOW_LABEL)',
            self.source,
        )
        # aria-pressed as well would be read as "Hide password, pressed".
        self.assertNotIn("aria-pressed", self.source)

    def test_submitting_or_leaving_the_page_hides_a_revealed_password(self):
        self.assertRegex(
            self.source, r'form\.addEventListener\(\s*"submit",\s*hide\s*\)'
        )
        self.assertRegex(
            self.source, r'window\.addEventListener\(\s*"pagehide",\s*hide\s*\)'
        )

    def test_password_is_kept_from_spellcheck_and_autocorrect(self):
        for attribute in (
            r'spellcheck:\s*"false"',
            r'autocorrect:\s*"off"',
            r'autocapitalize:\s*"none"',
        ):
            self.assertRegex(self.source, attribute)
        self.assertRegex(self.source, r"keepPrivate\(\s*input\s*\)")

    def test_hidden_fields_get_no_button(self):
        self.assertRegex(self.source, r'\.display\s*===\s*"none"')

    def test_icon_licence_is_kept(self):
        self.assertIn("ISC License", self.source)
