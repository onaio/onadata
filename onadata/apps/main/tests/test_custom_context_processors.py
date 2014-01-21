from django.conf import settings
from django.test import TestCase
from onadata.apps.main.context_processors import site_name


class CustomContextProcessorsTest(TestCase):
    def test_site_name(self):
        context = site_name(None)
        self.assertEqual(context, {'SITE_NAME': 'example.com'})
        restore_site_id = settings.SITE_ID
        settings.SITE_ID = 100
        context = site_name(None)
        self.assertEqual(context, {'SITE_NAME': 'example.org'})
        settings.SITE_ID = restore_site_id
