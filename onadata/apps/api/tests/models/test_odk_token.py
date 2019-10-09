"""
Test ODK Token module
"""
from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.api.tests.models.test_abstract_models import \
    TestAbstractModels


class TestODKToken(TestAbstractModels):
    def test_create_odk_token(self):
        """
        Test that ODK Tokens can be created
        """
        self._create_user_and_login()
        initial_count = ODKToken.objects.count()
        sample_key = 'df23hjk4'

        odk_token = ODKToken.objects.create(user=self.user, key=sample_key)

        self.assertEqual(odk_token.key, sample_key)
        self.assertEqual(initial_count + 1, ODKToken.objects.count())
