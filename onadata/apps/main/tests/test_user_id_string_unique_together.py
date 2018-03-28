import os

from django.db import IntegrityError
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm


class TestUserIdStringUniqueTogether(TestBase):

    def test_unique_together(self):
        """
        Multiple users can have the same survey, but id_strings of
        surveys must be unique for a single user.
        """
        self._create_user_and_login()
        self.this_directory = os.path.dirname(__file__)
        xls_path = os.path.join(self.this_directory,
                                "fixtures", "gps", "gps.xls")

        # first time
        self._publish_xls_file(xls_path)
        self.assertEquals(XForm.objects.count(), 1)

        # second time
        self.assertRaises(IntegrityError, self._publish_xls_file, xls_path)
        self.assertEquals(XForm.objects.count(), 1)
        self.client.logout()

        # first time
        self._create_user_and_login(username="carl", password="carl")
        self._publish_xls_file(xls_path)
        self.assertEquals(XForm.objects.count(), 2)
