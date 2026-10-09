# -*- coding: utf-8 -*-
"""The 401 body telling a client how to satisfy a gate."""

import logging

from oidc.stepup import find_step_up_auth_server

from onadata.libs.stepup.federated import start_step_up
from onadata.libs.stepup.policy import mode

logger = logging.getLogger(__name__)

#: How the client should obtain a grant.
DIALECT_LOCAL_TOTP = "local-totp"
DIALECT_OIDC = "oidc"


def build_challenge(action: str, user=None) -> dict:
    """What the client needs in order to satisfy ``action``'s gate.

    ``audience`` is the load-bearing part: the client echoes it back, and the
    grant it earns is spendable here and nowhere else.
    """
    body = {"error": "step_up_required", "audience": action}

    if mode() == "local":
        body["dialect"] = DIALECT_LOCAL_TOTP
        return body

    body["dialect"] = DIALECT_OIDC
    auth_server = find_step_up_auth_server()
    if not auth_server:
        logger.warning("step-up: federated mode but no auth server is configured")
        body["error"] = "step_up_unavailable"
        return body
    if user is None:
        # Nothing to bind the state to, so the callback could not tell whose
        # step-up it was completing.
        logger.warning("step-up: cannot start a federated flow for no user")
        body["error"] = "step_up_unavailable"
        return body

    try:
        url, _ = start_step_up(auth_server, action, user)
    except (ValueError, KeyError):
        # A server missing its endpoints. The client cannot be sent anywhere,
        # and a gated request must still answer rather than raise.
        logger.exception("step-up: cannot build an authorization request")
        body["error"] = "step_up_unavailable"
        return body

    body["authorizationUrl"] = url
    return body
