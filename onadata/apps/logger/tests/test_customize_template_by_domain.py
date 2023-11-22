from onadata.apps.main.tests.test_base import TestBase
from django.test import override_settings
from onadata.apps.logger.templatetags.customize_template_by_domain import settings_value

TEMPLATE_CUSTOMIZATION = {
    "*": {
        "app_name": "Ona",
        "login_logo": "/static/ona-logo.png",
        "favicon": "/static/ona-favicon-32x32.png",
    },
    "api.ona.io": {
        "login_background": "#009CDE",
        "app_name": "NCDS",
        "login_logo": "/static/who-logo.jpeg",
        "favicon": "/static/who-favicon-32x32.png",
    },
}


class TestCustomizeTemplateTasks(TestBase):
    """
    Test api tasks
    """

    @override_settings(TEMPLATE_CUSTOMIZATION=TEMPLATE_CUSTOMIZATION)
    @override_settings(ALLOWED_HOSTS=["api.ona.io"])
    def test_for_domain(self):
        """Test settings_value returns correct values"""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "api.ona.io"
        self.assertEqual(
            settings_value({"request": request}, "login_background"), "#009CDE"
        )
        self.assertEqual(settings_value({"request": request}, "app_name"), "NCDS")
        self.assertEqual(
            settings_value({"request": request}, "login_logo"), "/static/who-logo.jpeg"
        )
        self.assertEqual(
            settings_value({"request": request}, "favicon"),
            "/static/who-favicon-32x32.png",
        )

    @override_settings(TEMPLATE_CUSTOMIZATION=TEMPLATE_CUSTOMIZATION)
    @override_settings(ALLOWED_HOSTS=["*"])
    def test_for_no_domain(self):
        """Test settings_value returns correct values"""
        request = self.factory.get("/")
        self.assertEqual(settings_value({"request": request}, "login_background"), "")
        self.assertEqual(settings_value({"request": request}, "app_name"), "Ona")
        self.assertEqual(
            settings_value({"request": request}, "login_logo"), "/static/ona-logo.png"
        )
        self.assertEqual(
            settings_value({"request": request}, "favicon"),
            "/static/ona-favicon-32x32.png",
        )

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_for_no_domain_no_settings(self):
        """Test settings_value returns correct values"""
        request = self.factory.get("/")
        self.assertEqual(settings_value({"request": request}, "login_background"), "")
        self.assertEqual(settings_value({"request": request}, "app_name"), "")
        self.assertEqual(settings_value({"request": request}, "login_logo"), "")
        self.assertEqual(
            settings_value({"request": request}, "favicon"),
            "",
        )
