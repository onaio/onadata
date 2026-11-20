"""Every page base loads the script that adds Show/Hide to password inputs."""

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

SCRIPT = "js/password-toggle.js"


class TestPasswordToggleScript(TestCase):
    def _render(self, template_name):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        return render_to_string(template_name, request=request)

    def test_base_loads_the_script(self):
        self.assertIn(SCRIPT, self._render("base.html"))

    def test_ona_base_loads_the_script(self):
        self.assertIn(SCRIPT, self._render("ona_base.html"))
