from subprocess import call

from django.test import TestCase


class TestStyle(TestCase):

    def test_flake8(self):
        result = call(['flake8', '--exclude', 'migrations,src,settings', '.'])
        self.assertEqual(result, 0, "Code is not flake8.")
