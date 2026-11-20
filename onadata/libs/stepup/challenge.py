# -*- coding: utf-8 -*-
"""The 401 body telling a client how to satisfy a gate."""

import logging

from django.core.exceptions import ImproperlyConfigured

from oidc.stepup import find_step_up_auth_server

from onadata.libs.stepup.federated import start_step_up
from onadata.libs.stepup.gate import STEP_UP_REQUIRED
from onadata.libs.stepup.policy import is_local_mode

logger = logging.getLogger(__name__)

#: How a client should obtain a grant.
DIALECT_LOCAL_TOTP = "local-totp"
DIALECT_OIDC = "oidc"

#: The deployment cannot send the user anywhere to step up. This is a server
#: fault, so it is answered with a 503.
STEP_UP_UNAVAILABLE = "step_up_unavailable"


def build_challenge(action: str, user=None) -> dict:
    """The body a client needs to satisfy the gate on ``action``.

    The client echoes ``audience`` back. The grant it earns is valid for that
    action only.
    """
    body = {"error": STEP_UP_REQUIRED, "audience": action}

    if is_local_mode():
        body["dialect"] = DIALECT_LOCAL_TOTP
        return body

    body["dialect"] = DIALECT_OIDC
    auth_server = find_step_up_auth_server()
    if not auth_server:
        logger.warning("step-up: federated mode but no auth server is configured")
        body["error"] = STEP_UP_UNAVAILABLE
        return body
    if user is None or not user.is_authenticated:
        # Without a user, the callback cannot tell whose step-up it completes.
        logger.warning("step-up: cannot start a federated flow for no user")
        body["error"] = STEP_UP_UNAVAILABLE
        return body

    try:
        url, _ = start_step_up(auth_server, action, user)
    except (ValueError, KeyError, TypeError, ImproperlyConfigured):
        # The auth server is missing or malformed. Answer instead of raising.
        logger.exception("step-up: cannot build an authorization request")
        body["error"] = STEP_UP_UNAVAILABLE
        return body

    body["authorizationUrl"] = url
    return body
