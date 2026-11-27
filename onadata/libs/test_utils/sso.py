"""
Signed SSO tokens for tests.
"""

from datetime import datetime, timedelta, timezone

from django.conf import settings

import jwt

TOKEN_LIFETIME = timedelta(minutes=5)


def sso_token(email):
    """An SSO token signed with the key and algorithm in OPENID_CONNECT_VIEWSET_CONFIG.

    ona-oidc refuses a token without ``exp``.
    """
    config = settings.OPENID_CONNECT_VIEWSET_CONFIG
    issued_at = datetime.now(timezone.utc)
    return jwt.encode(
        {"email": email, "iat": issued_at, "exp": issued_at + TOKEN_LIFETIME},
        config["JWT_SECRET_KEY"],
        algorithm=config["JWT_ALGORITHM"],
    )
