"""
Backends module for th API app
"""
import logging

from django_digest.backend.storage import AccountStorage
from django_digest.models import PartialDigest

from django.conf import settings
from django.utils import timezone

from onadata.apps.api.models.odk_token import ODKToken

_l = logging.getLogger(__name__)
_l.setLevel(logging.DEBUG)

ODK_KEY_LIFETIME_IN_SEC = getattr(settings, 'ODK_KEY_LIFETIME', 7) * 86400


class DigestAccountStorage(AccountStorage):
    """
    Digest Account Backend class
    """

    def _check_odk_token_expiry(self, created):
        """
        Checks to see whether an ODK Token has expired
        """
        time_diff = (timezone.now() - created).total_seconds

        return time_diff > ODK_KEY_LIFETIME_IN_SEC

    def get_user(self, login):
        """
        Checks if there is a partial digest matching the login passed in and
        that the user associated with the Partial Digest is active.

        Also checks if an ODK Token has been set on the Users account and
        verifies that the ODK Token is active and hasn't expired.
        """
        pds = [
            pd for pd in PartialDigest.objects.filter(
                login=login, user__is_active=True)
            ]

        if len(pds) == 0:
            return None
        elif len(pds) > 1:
            _l.warn(f'Multiple partial digests found for the login {login}')
            return None

        user = pds[0].user

        try:
            odk_token = user.odk_token
        except AttributeError:
            pass
        else:
            if odk_token.status == ODKToken.INACTIVE or \
                    self._check_odk_token_expiry(odk_token.created):
                return None

        return user
