# -*- coding: utf-8 -*-
"""
Test increase_odk_token_lifetime command
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command

from six import StringIO

from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.main.tests.test_base import TestBase


class IncreaseODKTokenLifetimeTest(TestBase):
    """
    Test increase_odk_token_lifetime command
    """

    # pylint: disable=invalid-name
    def test_increase_odk_token_lifetime(self):
        """
        Test increase_odk_token_lifetime command
        """
        user = get_user_model().objects.create(
            username="dave", email="dave@example.com"
        )
        token = ODKToken.objects.create(user=user)
        expiry_date = token.expires

        out = StringIO()
        call_command(
            "increase_odk_token_lifetime", days=2, username=user.username, stdout=out
        )

        self.assertEqual(
            "Increased the lifetime of ODK Token for user dave\n", out.getvalue()
        )
        token.refresh_from_db()
        self.assertEqual(expiry_date + timedelta(days=2), token.expires)
