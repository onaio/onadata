import os
from datetime import timedelta

from django.conf import settings
from django.test.utils import override_settings
from django.utils import timezone

from cryptography.fernet import Fernet
from django_digest.test import DigestAuth

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.models import UserProfile
from onadata.apps.api.models.odk_token import ODKToken


ODK_TOKEN_STORAGE = 'onadata.apps.api.storage.ODKTokenAccountStorage'


class TestDigestAuthentication(TestBase):
    def setUp(self):
        super(TestBase, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()

    def test_authenticated_submissions(self):
        """
        xml_submission_file is the field name for the posted xml file.
        """
        s = self.surveys[0]
        xml_submission_file_path = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'
        )
        self._set_require_auth()
        auth = DigestAuth(self.login_username, self.login_password)
        self._make_submission(xml_submission_file_path, add_uuid=True,
                              auth=auth)
        self.assertEqual(self.response.status_code, 201)

    def _set_require_auth(self, auth=True):
        profile, created = \
            UserProfile.objects.get_or_create(user=self.user)
        profile.require_auth = auth
        profile.save()

    def test_fail_authenticated_submissions_to_wrong_account(self):
        username = 'dennis'
        # set require_auth b4 we switch user
        self._set_require_auth()
        self._create_user_and_login(username=username, password=username)
        self._set_require_auth()
        s = self.surveys[0]
        xml_submission_file_path = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'
        )

        self._make_submission(xml_submission_file_path, add_uuid=True,
                              auth=DigestAuth('alice', 'alice'))
        # Authentication required
        self.assertEqual(self.response.status_code, 401)
        auth = DigestAuth('dennis', 'dennis')
        self._make_submission(xml_submission_file_path, add_uuid=True,
                              auth=auth)
        # Not allowed
        self.assertEqual(self.response.status_code, 403)

    @override_settings(
        DIGEST_ACCOUNT_BACKEND=ODK_TOKEN_STORAGE
    )
    def test_digest_authentication_with_odk_token_storage(self):
        """
        Test that a valid Digest request with as the auth email:odk_token
        is authenticated
        """
        s = self.surveys[0]
        xml_submission_file_path = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'
        )
        self._set_require_auth()

        # Set email for user
        self.user.email = 'bob@bob.test'
        self.user.save()
        odk_token = ODKToken.objects.create(user=self.user)

        # The value odk_token.key is hashed we need to have the raw_key
        # In order to authenticate with DigestAuth
        fernet = Fernet(getattr(settings, 'ODK_TOKEN_FERNET_KEY'))
        raw_key = fernet.decrypt(odk_token.key.encode('utf-8')).decode('utf-8')

        auth = DigestAuth(self.user.email, raw_key)
        self._make_submission(xml_submission_file_path, add_uuid=True,
                              auth=auth)
        self.assertEqual(self.response.status_code, 201)

        # Test can authenticate with username:token
        s = self.surveys[1]
        xml_submission_file_path = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'
        )

        auth = DigestAuth(self.user.username, raw_key)
        self._make_submission(xml_submission_file_path, add_uuid=True,
                              auth=auth)
        self.assertEqual(self.response.status_code, 201)

    @override_settings(
        ODK_KEY_LIFETIME=1,
        DIGEST_ACCOUNT_BACKEND=ODK_TOKEN_STORAGE
    )
    def test_fails_authentication_past_odk_token_expiry(self):
        """
        Test that a Digest authenticated request using an ODK Token that has
        expired is not authorized
        """
        s = self.surveys[0]
        xml_submission_file_path = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', s, s + '.xml'
        )
        self._set_require_auth()

        # Set email for user
        self.user.email = 'bob@bob.test'
        self.user.save()
        odk_token = ODKToken.objects.create(user=self.user)

        odk_token.created = timezone.now() - timedelta(days=400)
        odk_token.save()

        # The value odk_token.key is hashed we need to have the raw_key
        # In order to authenticate with DigestAuth
        fernet = Fernet(getattr(settings, 'ODK_TOKEN_FERNET_KEY'))
        raw_key = fernet.decrypt(odk_token.key.encode('utf-8')).decode('utf-8')

        auth = DigestAuth(self.user.email, raw_key)
        self._make_submission(xml_submission_file_path, add_uuid=True,
                              auth=auth)
        self.assertEqual(self.response.status_code, 401)
