from onadata.apps.api.tests.models.test_abstract_models import (
    TestAbstractModels)
from onadata.apps.api.models import TempToken
from django.db.utils import IntegrityError


class TestTempToken(TestAbstractModels):

    def test_temp_token_creation(self):
        initial_count = TempToken.objects.count()
        self._create_user_and_login()
        token, created = TempToken.objects.get_or_create(
            user=self.user, key='456c27c7d59303aed1dffd3b5ffaad36f0676618')

        self.assertEqual(token.key, '456c27c7d59303aed1dffd3b5ffaad36f0676618')
        self.assertTrue(created)
        self.assertEquals(initial_count + 1, TempToken.objects.count())

        # update initial count
        initial_count = TempToken.objects.count()

        # for some reason token cannot be updated; trigger error in issue #629
        # on core
        with self.assertRaises(IntegrityError):
            token.key = '1b3b82a23063a8a4e64fb4434dc21ab181fbbe7c'
            token.save()

        # for some reason, <instance>.delete() doesn't work
        token.delete()
        with self.assertRaises(IntegrityError):
            token1, created1 = TempToken.objects.get_or_create(
                user=self.user, key='1b3b82a23063a8a4e64fb4434dc21ab181fbbe7c')

        # this works
        TempToken.objects.get(
            user=self.user,
            key='456c27c7d59303aed1dffd3b5ffaad36f0676618').delete()
        self.assertEquals(initial_count - 1, TempToken.objects.count())
        token1, created1 = TempToken.objects.get_or_create(
            user=self.user, key='1b3b82a23063a8a4e64fb4434dc21ab181fbbe7c')

        self.assertEqual(
            token1.key, '1b3b82a23063a8a4e64fb4434dc21ab181fbbe7c')
        self.assertTrue(created1)
