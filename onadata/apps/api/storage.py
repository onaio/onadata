# -*- coding: utf-8 -*-
"""
Storage module for the api app
"""
import logging

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from django_digest.backend.storage import AccountStorage

from onadata.apps.api.models.odk_token import ODKToken

_l = logging.getLogger(__name__)
_l.setLevel(logging.WARNING)

ODK_KEY_LIFETIME_IN_SEC = getattr(settings, "ODK_KEY_LIFETIME", 7) * 86400


class ODKTokenAccountStorage(AccountStorage):
    """
    Digest Account Backend class

    In order to utilize this storage as the default account storage for
    Digest Authentication set the DIGEST_ACCOUNT_BACKEND variable in
    your local_settings to 'onadata.apps.api.storage.ODKTokenAccountStorage'
    """

    GET_PARTIAL_DIGEST_QUERY = f"""
    SELECT django_digest_partialdigest.login,
     django_digest_partialdigest.partial_digest
      FROM django_digest_partialdigest
      INNER JOIN auth_user ON
        auth_user.id = django_digest_partialdigest.user_id
      INNER JOIN api_odktoken ON
        api_odktoken.user_id = django_digest_partialdigest.user_id
      WHERE django_digest_partialdigest.login = %s
        AND django_digest_partialdigest.confirmed
        AND auth_user.is_active
        AND api_odktoken.status='{ODKToken.ACTIVE}'
    """

    def get_partial_digest(self, username):
        """
        Checks that the returned partial digest is associated with a
        Token that isn't past it's expire date.

        Sets an ODK Token to Inactive if the associate token has passed
        its expiry date
        """
        cursor = connection.cursor()
        cursor.execute(self.GET_PARTIAL_DIGEST_QUERY, [username])
        # In MySQL, string comparison is case-insensitive by default.
        # Therefore a second round of filtering is required.
        partial_digest = [(row[1]) for row in cursor.fetchall() if row[0] == username]
        if not partial_digest:
            return None

        try:
            token = ODKToken.objects.get(
                Q(user__username=username) | Q(user__email=username),
                status=ODKToken.ACTIVE,
            )
        except MultipleObjectsReturned:
            _l.error("User %s has multiple ODK Tokens", username)
            return None
        except ODKToken.DoesNotExist:
            _l.error("User %s has no active ODK Token", username)
            return None
        if timezone.now() > token.expires:
            token.status = ODKToken.INACTIVE
            token.save()
            return None

        return partial_digest[0]
