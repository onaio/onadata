from django.conf import settings
from django.test import TestCase
from formhub.context_processors import site_name


class CustomContextProcessorsTest(TestCase):
    def test_site_name(self):
        context = site_name(None)
        self.assertEqual(context, {'SITE_NAME': 'example.com'})
        settings.SITE_ID = 100
        context = site_name(None)
        self.assertEqual(context, {'SITE_NAME': 'example.org'})
