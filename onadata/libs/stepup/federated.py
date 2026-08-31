# -*- coding: utf-8 -*-
"""Start a step-up against an external identity provider.

The protocol lives in ona-oidc (``oidc.stepup``); this fixes what OnaData
carries across the redirect.
"""

from oidc.stepup import build_step_up_url


def start_step_up(auth_server: str, audience: str, user) -> tuple[str, str]:
    """Build the authorize URL that will prove a second factor.

    Returns ``(url, state)``. The audience and the user ride along in the
    state because the provider redirects back to a URL, not to the control the
    user clicked.
    """
    return build_step_up_url(
        auth_server, context={"audience": audience, "user_pk": user.pk}
    )
