from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils.six import StringIO

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.models.odk_token import ODKToken


class IncreaseODKTokenLifetimeTest(TestBase):
    def test_increase_odk_token_lifetime(self):
        user = User.objects.create(
            username='dave', email='dave@example.com')
        token = ODKToken.objects.create(user=user)
        expiry_date = token.expires

        out = StringIO()
        call_command(
            'increase_odk_token_lifetime',
            days=2,
            username=user.username,
            stdout=out
        )

        self.assertEqual(
            'Increased the lifetime of ODK Token for user dave\n',
            out.getvalue())
        token.refresh_from_db()
        self.assertEqual(expiry_date + timedelta(days=2), token.expires)
