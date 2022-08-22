from subprocess import call, check_output

from django.test import TestCase


class TestStyle(TestCase):

    def test_flake8(self):
        result = call(
            ['flake8', '--exclude=migrations,src,settings', 'onadata']
        )
        print(
            check_output(
                ['flake8', '--exclude=migrations,src,settings', 'onadata']
            )
        )
        print(f"{result}")
        self.assertEqual(result, 0, "Code is not flake8.")
